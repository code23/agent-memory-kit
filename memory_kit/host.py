"""Private macOS installation of a dedicated, owned PostgreSQL instance.

All database credentials live only in Keychain and child environments/stdin.
No subprocess diagnostics are surfaced: drivers may include credentials in them.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import pwd
import re
import shlex
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import sys
from types import SimpleNamespace
import uuid
from urllib.parse import parse_qs, urlencode, urlsplit

from . import security
from .keychain import MacKeychain

PG_PORT = 47893
SERVICE_PORT = 47892
ROLES = {"bootstrap": "amk_bootstrap", "reader": "memory_reader",
         "submitter": "memory_submitter", "operator": "memory_operator"}
DATABASE = "agent_memory"
RUNTIME_FILES = ("team-memory-manifest.json", "team-memory-server.mjs",
                 "team-memory-bootstrap.mjs", "team-memory-operator.mjs",
                 "team-memory-recovery.mjs", "team-memory-verify.mjs")


class HostError(RuntimeError):
    """Safe, non-secret operator diagnostic."""


def clean_env(extra=None):
    """Discard inherited libpq, Node injection and Python injection settings."""
    allowed = ("HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "LC_ALL")
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    account = pwd.getpwuid(os.getuid())
    env.update(HOME=account.pw_dir, USER=account.pw_name, LOGNAME=account.pw_name)
    env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    if extra:
        env.update(extra)
    return env


def command(argv, *, input=None, env=None, capture=True, check=True):
    try:
        result = subprocess.run([str(item) for item in argv], input=input,
                                env=clean_env(env), stdout=subprocess.PIPE if capture else None,
                                stderr=subprocess.PIPE if capture else None,
                                timeout=120 if capture else None, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise HostError("A required local command could not run") from None
    if check and result.returncode:
        raise HostError("A required local command failed; no diagnostic payload was exposed")
    return result


def _private_file(path, uid):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != uid or info.st_mode & 0o077:
        raise HostError("An installation file is not owner-private")


def _write_new(path, payload):
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _save_config(path, config, uid):
    if path.exists():
        _private_file(path, uid)
    config = {key: value for key, value in config.items() if key != "pg_tools"}
    temporary = path.with_name(".config-" + secrets.token_hex(8))
    _write_new(temporary, (json.dumps(config, sort_keys=True, indent=2) + "\n").encode())
    os.replace(str(temporary), str(path))
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _free_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind(("127.0.0.1", port))
        except OSError:
            raise HostError("A required loopback port is occupied") from None


def _source_files(kit):
    files = [kit / "runtime" / name for name in RUNTIME_FILES]
    files += sorted((kit / "memory_kit").glob("*.py"))
    files += [kit / "memory-kit"]
    return files


def software_hash(kit):
    digest = hashlib.sha256()
    for directory in (kit, kit / "runtime", kit / "memory_kit"):
        if directory.is_symlink() or not directory.is_dir():
            raise HostError("Installer source directories must be real directories")
    for file in _source_files(kit):
        if file.is_symlink() or not file.is_file():
            raise HostError("Installer source files must be regular files")
        digest.update(str(file.relative_to(kit)).encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()


def _protect_selector(path, identity):
    path = Path(path)
    if not path.is_absolute():
        raise HostError("Tool selectors must be absolute paths")
    pending = list(path.parts[1:])
    current = Path("/")
    hops = 0
    while pending:
        part = pending.pop(0)
        if part == ".":
            continue
        if part == "..":
            current = current.parent
            continue
        candidate = current / part
        try:
            info = candidate.lstat()
        except OSError:
            raise HostError("An explicit executable path is unavailable") from None
        if stat.S_ISLNK(info.st_mode):
            security.assert_not_agent_writable(current, identity)
            hops += 1
            if hops > 40:
                raise HostError("Tool selector has a cyclic or excessive symlink chain")
            try:
                target = Path(os.readlink(candidate))
            except OSError:
                raise HostError("An explicit executable path is unavailable") from None
            if target.is_absolute():
                current = Path("/")
                pending = list(target.parts[1:]) + pending
            else:
                pending = list(target.parts) + pending
        else:
            current = candidate
    security.assert_not_agent_writable(current, identity)
    return current


def _tool(path, identity):
    path = _protect_selector(path, identity)
    if not path.is_absolute() or not path.is_file() or not os.access(str(path), os.X_OK):
        raise HostError("An explicit executable path is unavailable")
    path = path.resolve(strict=True)
    security.assert_not_agent_writable(path, identity)
    return str(path)


def default_root(workspace):
    return Path(pwd.getpwuid(os.getuid()).pw_dir).resolve() / "Library" / "Application Support" / "Agent Memory Kit" / workspace


def _read_config(root, kit, uid):
    security.assert_private_root(root, kit, uid)
    path = root / "config.json"
    _private_file(path, uid)
    try:
        config = json.loads(path.read_text())
        if (config["format"] != 1 or config["owner_uid"] != uid or
                config["root"] != str(root) or config["pg_port"] != PG_PORT or
                config["service_port"] != SERVICE_PORT or config["database"] != DATABASE or
                str(uuid.UUID(config["instance"])) != config["instance"] or
                len(config["software_hash"]) != 64 or
                any(ch not in "0123456789abcdef" for ch in config["software_hash"])):
            raise ValueError()
        security.validate_workspace(config["workspace"])
        if config["owner_id"] != "owner-" + config["instance"]:
            raise ValueError()
    except (KeyError, ValueError, TypeError, OSError):
        raise HostError("Installation configuration is invalid") from None
    return config


def plan(workspace, coding_user, root=None, pg_bin=None, node=None, kit=None, keychain=None):
    """Read-only preflight. No directories, accounts, credentials or services created."""
    if platform.system() != "Darwin":
        raise HostError("The host installer requires macOS")
    security.validate_workspace(workspace)
    uid = os.getuid()
    if uid == 0:
        raise HostError("Run as the separate operator account, without sudo")
    identity = security.coding_identity(coding_user, uid)
    kit = Path(kit or Path(__file__).resolve().parent.parent)
    root = Path(root) if root is not None else default_root(workspace)
    security.assert_private_root(root, kit, uid)
    _check_socket_path(root)
    if root.exists() and not (root / "config.json").exists() and any(root.iterdir()):
        raise HostError("Refusing an unmarked nonempty installation directory")
    for file in _source_files(kit):
        security.assert_not_agent_writable(file, identity)
    node_selector = str(node or shutil.which("node") or "")
    pg_selector = Path(pg_bin) if pg_bin else Path(shutil.which("initdb") or "").parent
    _protect_selector(pg_selector, identity)
    pg_dir = pg_selector.resolve(strict=True)
    security.assert_not_agent_writable(pg_dir, identity)
    node_path = _tool(node_selector, identity)
    pg_tools = {name: _tool(pg_dir / name, identity)
                for name in ("initdb", "pg_ctl", "psql", "postgres")}
    python_selector = str(Path(sys.executable))
    python = _tool(python_selector, identity)
    version = command([node_path, "--version"]).stdout.decode().strip()
    if not version.startswith("v24."):
        raise HostError("Node.js 24 is required; install prerequisites separately")
    for name in ("initdb", "pg_ctl", "psql", "postgres"):
        version = command([pg_tools[name], "--version"]).stdout.decode().strip()
        if not re.search(r"\(PostgreSQL\) 18\.[0-9]+(?:\s|$)", version):
            raise HostError("PostgreSQL 18 tools are required")
    command([node_path, kit / "runtime/team-memory-verify.mjs"])
    digest = software_hash(kit)
    existing = None
    if (root / "config.json").exists():
        existing = _read_config(root, kit, uid)
        if (existing["workspace"] != workspace or existing["coding_uid"] != identity["uid"] or
                existing.get("node_selector", existing["node"]) != node_selector or
                existing.get("pg_selector", existing["pg_bin"]) != str(pg_selector) or
                existing["software_hash"] != digest):
            raise HostError("Installation identity or version differs; upgrades require a recovery-backed release")
        # Never operate against a cluster that might still be serving requests.
        if _pg_status(existing).returncode != 3:
            raise HostError("Stop this instance before installing again")
    _free_port(SERVICE_PORT)
    (keychain or MacKeychain()).check_ready()
    return {"workspace": workspace, "coding_uid": identity["uid"], "owner_uid": uid,
            "root": str(root), "pg_bin": str(pg_dir), "node": node_path,
            "python": python, "node_selector": node_selector, "pg_selector": str(pg_selector),
            "python_selector": python_selector, "pg_tools": pg_tools,
            "software_hash": digest, "existing": existing,
            "kit": str(kit)}


def _software(config):
    return Path(config["root"]) / "software" / config["software_hash"]


def _pg(config, *args, check=True):
    return command([config["pg_tools"]["pg_ctl"], "-D", Path(config["root"]) / "postgres", *args],
                   check=check)


def _pg_status(config):
    data = Path(config["root"]) / "postgres"
    security.assert_private_root(data, Path(__file__).resolve().parent.parent, config["owner_uid"])
    if not (data / "postmaster.pid").exists():
        return SimpleNamespace(returncode=3)
    _private_file(data / "postmaster.pid", config["owner_uid"])
    try:
        identity = _coding_identity(config)
        selector = Path(config.get("pg_selector", config["pg_bin"]))
        binary = _tool(selector / "pg_ctl", identity)
        version = command([binary, "--version"]).stdout.decode()
        if not re.search(r"\(PostgreSQL\) 18\.[0-9]+(?:\s|$)", version):
            raise HostError("PostgreSQL 18 tools are required")
        local = dict(config, pg_tools={"pg_ctl": binary})
        result = _pg(local, "status", check=False)
        return SimpleNamespace(returncode=result.returncode if result.returncode in (0, 3) else 4)
    except (HostError, security.SecurityError, OSError):
        # Unknown is distinct from stopped; no unverified PID signaling.
        return SimpleNamespace(returncode=4)


def _stop_owned_pg(config, *, check=True):
    result = _pg_status(config)
    if result.returncode == 4:
        raise HostError("PostgreSQL tools are unavailable; restore PostgreSQL 18 to stop the owned cluster")
    if result.returncode == 0:
        selector = Path(config.get("pg_selector", config["pg_bin"]))
        binary = _tool(selector / "pg_ctl", _coding_identity(config))
        _pg(dict(config, pg_tools={"pg_ctl": binary}), "-w", "-t", "30", "-m", "fast", "stop", check=check)


def _cleanup_pg(config):
    """Best-effort shutdown of a verified postmaster; preserve the startup error."""
    try:
        if (Path(config["root"]) / "postgres/postmaster.pid").exists():
            _stop_owned_pg(config, check=False)
    except (HostError, security.SecurityError, OSError):
        pass


def _cluster_signature(config):
    data = Path(config["root"]) / "postgres"
    security.assert_private_root(data, Path(__file__).resolve().parent.parent, config["owner_uid"])
    _private_file(data / ".amk-initdb-complete", config["owner_uid"])
    _private_file(data / "PG_VERSION", config["owner_uid"])
    if (data / "PG_VERSION").read_text().strip() != "18":
        raise HostError("Owned PostgreSQL data version differs")
    signature = {}
    for name in ("postgresql.conf", "postgresql.auto.conf", "pg_hba.conf", "pg_ident.conf"):
        path = data / name
        _private_file(path, config["owner_uid"])
        signature[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    if config.get("cluster_config") is not None and config["cluster_config"] != signature:
        raise HostError("Owned PostgreSQL configuration differs from its journal")
    return signature


def _validate_pg_custody(config):
    root = Path(config["root"])
    security.assert_private_root(root, Path(__file__).resolve().parent.parent, config["owner_uid"])
    data = root / "postgres"
    security.ensure_private_directory(data, config["owner_uid"])


def _start_pg(config):
    _cluster_signature(config)
    socket_dir = _socket_directory(config, create=True)
    # /dev/null prevents query/error text from becoming a persistent secret-bearing log.
    _pg(config, "-w", "-t", "30", "-l", "/dev/null", "-o",
        "-h '' -p %d -k %s -c unix_socket_permissions=0700 -c logging_collector=off -c log_statement=none -c log_min_messages=panic -c log_min_error_statement=panic" % (PG_PORT, shlex.quote(str(socket_dir))),
        "start")


def _check_socket_path(root):
    # Darwin sockaddr_un.sun_path is 104 bytes, including its trailing NUL.
    if len(os.fsencode(str(Path(root) / "s" / (".s.PGSQL.%d" % PG_PORT)))) >= 104:
        raise HostError("Installation path is too long for a private macOS socket; select a shorter root")


def _socket_directory(config, create=False):
    path = Path(config["root"]) / "s"
    _check_socket_path(config["root"])
    if create:
        security.ensure_private_directory(path, config["owner_uid"])
    else:
        security.assert_private_root(path, Path(__file__).resolve().parent.parent, config["owner_uid"])
    return path


def _dsn(config, role, password):
    return "postgresql://%s:%s@localhost:%d/%s?%s" % (
        role, password, PG_PORT, DATABASE, urlencode({"host": str(_socket_directory(config))}))


def _database_env(config, dsn):
    """Translate the validated full URI to this bundled driver's Unix-socket contract.

    postgres.js does not honor libpq's ?host=/socket URI option. An empty URI
    hostname selects PGHOST, which its parser translates to a Unix socket path.
    No credential or TCP hostname is passed in DATABASE_URL.
    """
    parsed = urlsplit(dsn)
    return {"DATABASE_URL": "postgresql:///" + DATABASE,
            "PGHOST": str(_socket_directory(config)), "PGPORT": str(PG_PORT),
            "PGUSER": parsed.username, "PGPASSWORD": parsed.password}


def credential(config, key, keychain=None):
    value = (keychain or MacKeychain()).get(config["instance"], key)
    if value is None:
        raise HostError("An installation credential is unavailable in Keychain")
    try:
        text = value.decode("ascii")
        parsed = urlsplit(text)
        if (parsed.scheme != "postgresql" or parsed.hostname != "localhost" or
                parsed.port != PG_PORT or parsed.path != "/" + DATABASE or
                parsed.username != ROLES[key] or parsed.fragment or
                parse_qs(parsed.query, strict_parsing=True) != {"host": [str(_socket_directory(config))]} or
                not parsed.password or
                len(parsed.password) != 64 or any(c not in "0123456789abcdef" for c in parsed.password)):
            raise ValueError()
    except (ValueError, UnicodeError, KeyError):
        raise HostError("An installation credential does not match this instance") from None
    return text


def _psql(config, password, database, sql):
    return command([config["pg_tools"]["psql"], "-X", "--no-password",
                    "-v", "ON_ERROR_STOP=1", "-h", str(_socket_directory(config)), "-p", str(PG_PORT),
                    "-U", ROLES["bootstrap"], "-d", database],
                   input=sql.encode(), env={"PGPASSWORD": password})


def _bootstrap(config, secrets_by_role):
    password = urlsplit(secrets_by_role["bootstrap"]).password
    # Role names are fixed; passwords are locally generated hex, validated on retrieval.
    sql = "BEGIN;\n"
    sql += "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='amk_owner') THEN CREATE ROLE amk_owner NOLOGIN; END IF; END $$;\n"
    for profile in ("reader", "submitter", "operator"):
        role = ROLES[profile]
        role_password = urlsplit(secrets_by_role[profile]).password
        sql += ("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='%s') THEN "
                "CREATE ROLE %s LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD '%s'; "
                "END IF; END $$;\n") % (role, role, role_password)
    sql += "COMMIT;\n"
    _psql(config, password, "postgres", sql)
    # psql conditional execution avoids attempting CREATE DATABASE in a transaction.
    _psql(config, password, "postgres",
           "SELECT 'CREATE DATABASE agent_memory OWNER amk_owner' WHERE NOT EXISTS "
           "(SELECT FROM pg_database WHERE datname = 'agent_memory')\\gexec\n")
    _psql(config, password, DATABASE,
           "REVOKE ALL ON DATABASE agent_memory FROM PUBLIC;\n"
           "REVOKE CREATE ON SCHEMA public FROM PUBLIC;\n"
           "GRANT CONNECT ON DATABASE agent_memory TO memory_reader, memory_submitter, memory_operator;\n")
    command([config["node"], _software(config) / "runtime/team-memory-bootstrap.mjs",
             "--workspace", config["workspace"], "--name", config["workspace"],
             "--owner", config["owner_id"], "--reader-role", ROLES["reader"],
             "--submitter-role", ROLES["submitter"], "--operator-role", ROLES["operator"]],
            env=_database_env(config, secrets_by_role["bootstrap"]))


def _copy_software(kit, config):
    destination = _software(config)
    security.ensure_private_directory(destination.parent, config["owner_uid"])
    if destination.exists():
        security.ensure_private_directory(destination, config["owner_uid"])
        if software_hash(destination) != config["software_hash"]:
            raise HostError("Installed software differs from its recorded version")
        return
    # A failed or interrupted copy never occupies the final, versioned directory.
    staging = destination.parent / (".install-" + secrets.token_hex(16))
    security.ensure_private_directory(staging, config["owner_uid"])
    try:
        for file in _source_files(kit):
            target = staging / file.relative_to(kit)
            security.ensure_private_directory(target.parent, config["owner_uid"])
            _write_new(target, file.read_bytes())
        if software_hash(staging) != config["software_hash"]:
            raise HostError("Installed software verification failed")
        command([config["node"], staging / "runtime/team-memory-verify.mjs"])
        os.rename(str(staging), str(destination))
    finally:
        if staging.exists():
            shutil.rmtree(str(staging))


def install(preflight, keychain=None):
    """Install/resume only a preflighted matching instance; never delete its database."""
    tools = preflight.get("pg_tools")
    if not isinstance(tools, dict) or set(tools) != {"initdb", "pg_ctl", "psql", "postgres"}:
        raise HostError("Verified PostgreSQL preflight tools are required")
    keychain = keychain or MacKeychain()
    keychain.check_ready()
    root, kit = Path(preflight["root"]), Path(preflight["kit"])
    uid = preflight["owner_uid"]
    security.assert_private_root(root, kit, uid)
    if software_hash(kit) != preflight["software_hash"]:
        raise HostError("Installer source changed after preflight")
    security.ensure_private_directory(root, uid)
    lock_path = root / ".install.lock"
    lock_fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        _private_file(lock_path, uid)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise HostError("Another installation operation is running") from None
        config = preflight["existing"]
        if (root / "config.json").exists():
            disk = _read_config(root, kit, uid)
            if config is None or disk != {key: value for key, value in config.items() if key != "pg_tools"}:
                raise HostError("Installation changed after preflight")
        elif config is not None:
            raise HostError("Installation changed after preflight")
        else:
            config = {key: preflight[key] for key in ("workspace", "coding_uid", "owner_uid", "root",
                                                       "pg_bin", "node", "python", "software_hash")}
            for key in ("node_selector", "pg_selector", "python_selector", "pg_tools"):
                if key in preflight:
                    config[key] = preflight[key]
            config.update(format=1, instance=str(uuid.uuid4()), pg_port=PG_PORT,
                          service_port=SERVICE_PORT, database=DATABASE, phase="prepared")
            config["owner_id"] = "owner-" + config["instance"]
            _save_config(root / "config.json", config, uid)
        for key in ("node", "python", "python_selector", "pg_bin", "pg_tools"):
            if key in preflight:
                config[key] = preflight[key]
        _copy_software(kit, config)
        values = {}
        for profile, role in ROLES.items():
            if keychain.get(config["instance"], profile) is None:
                if config["phase"] != "prepared":
                    raise HostError("Existing credentials are missing; restore through recovery")
                keychain.put(config["instance"], profile, _dsn(config, role, secrets.token_hex(32)).encode())
            values[profile] = credential(config, profile, keychain)
        data = root / "postgres"
        if not data.exists():
            if config["phase"] != "prepared":
                raise HostError("Existing database is missing; restore through recovery")
            staging_data = root / (".initdb-" + secrets.token_hex(16))
            try:
                command([config["pg_tools"]["initdb"],
                         "-D", staging_data, "--encoding=UTF8",
                         "--auth-local=scram-sha-256", "--auth-host=scram-sha-256",
                         "--username=" + ROLES["bootstrap"], "--pwfile=/dev/stdin"],
                        input=(urlsplit(values["bootstrap"]).password + "\n").encode())
                security.ensure_private_directory(staging_data, uid)
                _write_new(staging_data / ".amk-initdb-complete", b"1\n")
                os.rename(str(staging_data), str(data))
            finally:
                if staging_data.exists():
                    shutil.rmtree(str(staging_data))
        elif not (data / ".amk-initdb-complete").is_file():
            raise HostError("Partial database initialization requires operator recovery")
        security.ensure_private_directory(data, uid)
        config["cluster_config"] = _cluster_signature(config)
        if config["phase"] != "installed":
            config["phase"] = "cluster_ready"
        _save_config(root / "config.json", config, uid)
        _validate_pg_custody(config)
        try:
            _start_pg(config)
            _bootstrap(config, values)
            config["phase"] = "installed"
            _save_config(root / "config.json", config, uid)
        finally:
            _cleanup_pg(config)
        return {"installed": True, "workspace": config["workspace"], "data_preserved": True}
    finally:
        os.close(lock_fd)


def load(root, kit=None, runtime=True):
    kit = Path(kit or Path(__file__).resolve().parent.parent)
    config = _read_config(Path(root), kit, os.getuid())
    if not runtime:
        return config
    identity = _coding_identity(config)
    config["node"] = _tool(config.get("node_selector", config["node"]), identity)
    config["python"] = _tool(config.get("python_selector", config["python"]), identity)
    selector = Path(config.get("pg_selector", config["pg_bin"]))
    _protect_selector(selector, identity)
    security.assert_not_agent_writable(selector.resolve(strict=True), identity)
    config["pg_bin"] = str(selector.resolve(strict=True))
    config["pg_tools"] = {name: _tool(selector / name, identity)
                          for name in ("initdb", "pg_ctl", "psql", "postgres")}
    if not command([config["node"], "--version"]).stdout.decode().startswith("v24."):
        raise HostError("The configured Node.js version must remain on major 24")
    for binary in config["pg_tools"].values():
        if not re.search(r"\(PostgreSQL\) 18\.[0-9]+(?:\s|$)", command([binary, "--version"]).stdout.decode()):
            raise HostError("The configured PostgreSQL version must remain on major 18")
    if config["phase"] != "installed":
        raise HostError("Installation is incomplete; resume install before service use")
    if software_hash(_software(config)) != config["software_hash"]:
        raise HostError("Installed software differs from its recorded version")
    command([config["node"], _software(config) / "runtime/team-memory-verify.mjs"])
    return config


def _coding_identity(config):
    try:
        name = pwd.getpwuid(config["coding_uid"]).pw_name
    except (KeyError, TypeError):
        raise HostError("The configured coding account is unavailable") from None
    return security.coding_identity(name, os.getuid())


def label(config):
    return "org.agent-memory-kit." + config["instance"]


def _plist_path(config):
    return Path(pwd.getpwuid(os.getuid()).pw_dir).resolve() / "Library/LaunchAgents" / (label(config) + ".plist")


def _launch_target(config):
    return "gui/%d/%s" % (config["owner_uid"], label(config))


def _launch_payload(config):
    return {"Label": label(config), "ProgramArguments": [config["python"], "-I",
            str(_software(config) / "memory-kit"), "daemon", "--root", config["root"]],
            "RunAtLoad": True, "KeepAlive": False,
            "StandardOutPath": "/dev/null", "StandardErrorPath": "/dev/null"}


def _matching_plist(config):
    path = _plist_path(config)
    if path.exists() or path.is_symlink():
        _private_file(path, config["owner_uid"])
        actual = plistlib.loads(path.read_bytes())
        expected = _launch_payload(config)
        args = actual.get("ProgramArguments", [])
        if args and isinstance(args[0], str) and Path(args[0]).is_absolute():
            expected["ProgramArguments"][0] = args[0]
        if actual != expected:
            raise HostError("An existing launch agent does not match this instance")
    return path


def start(config):
    path = _matching_plist(config)
    if not path.parent.exists():
        security.ensure_private_directory(path.parent, config["owner_uid"])
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise HostError("The operator LaunchAgents path is not a real directory")
    security.assert_not_agent_writable(path.parent, _coding_identity(config))
    # A completed or crashed launchd job remains loaded. Drain that exact label
    # before bootstrapping; start also safely restarts an already running job.
    stop(config)
    _free_port(SERVICE_PORT)
    _write_new(path, plistlib.dumps(_launch_payload(config)))
    try:
        command(["/bin/launchctl", "bootstrap", "gui/%d" % config["owner_uid"], path])
    except HostError:
        path.unlink()
        raise
    return {"service_loaded": True}


def status(config):
    result = command(["/bin/launchctl", "print", _launch_target(config)], check=False)
    pg = _pg_status(config)
    plist = _matching_plist(config)
    missing_python = plist.exists() and not Path(plistlib.loads(plist.read_bytes())["ProgramArguments"][0]).is_file()
    return {"service_loaded": result.returncode == 0, "autostart_python_missing": missing_python,
            "postgres_running": None if pg.returncode == 4 else pg.returncode == 0,
            "starts_at_login": _matching_plist(config).exists()}


def stop(config):
    path = _matching_plist(config)
    loaded = command(["/bin/launchctl", "print", _launch_target(config)], check=False)
    if loaded.returncode == 0:
        command(["/bin/launchctl", "bootout", _launch_target(config)])
    # Disable autostart even when a removed PostgreSQL tool blocks shutdown.
    if path.exists():
        path.unlink()
    _stop_owned_pg(config)
    return {"stopped": True, "data_preserved": True, "starts_at_login": False}


def uninstall(config):
    stop(config)
    software = _software(config)
    if software.parent.exists():
        for retired in software.parent.glob(".removed-*"):
            if not re.fullmatch(r"\.removed-[0-9a-f]{32}", retired.name):
                continue
            security.ensure_private_directory(retired, config["owner_uid"])
            shutil.rmtree(str(retired))
    if not software.exists():
        return {"uninstalled_service": True, "software_removed": True, "data_preserved": True,
                "configuration_and_keychain_preserved": True}
    security.ensure_private_directory(software, config["owner_uid"])
    if software_hash(software) != config["software_hash"]:
        raise HostError("Installed software differs; refusing to remove it")
    retired = software.parent / (".removed-" + secrets.token_hex(16))
    os.rename(str(software), str(retired))
    shutil.rmtree(str(retired))
    return {"uninstalled_service": True, "software_removed": True, "data_preserved": True,
            "configuration_and_keychain_preserved": True}


def daemon(config, keychain=None):
    """launchd child: own PostgreSQL, retrieve only submitter credentials, drain on stop."""
    dsn = credential(config, "submitter", keychain)
    _validate_pg_custody(config)
    child = None
    stopping = False
    def shutdown(signum, frame):
        nonlocal stopping
        stopping = True
        if child is not None:
            child.terminate()
    previous = {sig: signal.signal(sig, shutdown) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        _start_pg(config)
        if stopping:
            return 0
        child = subprocess.Popen([config["node"], str(_software(config) / "runtime/team-memory-server.mjs"),
                                  "--allow-submissions"],
                                 env=clean_env(dict(_database_env(config, dsn), PORT=str(SERVICE_PORT))),
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if stopping:
            child.terminate()
        return child.wait()
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        try:
            _cleanup_pg(config)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


def operator(config, argv, keychain=None):
    token_pipe = (argv[:2] == ["tokens", "create"] and
                  stat.S_ISFIFO(os.fstat(sys.stdout.fileno()).st_mode))
    if not sys.stdin.isatty() or (not sys.stdout.isatty() and not token_pipe):
        raise HostError("Operator review requires an interactive terminal")
    if argv[:2] == ["tokens", "create"] and not token_pipe:
        raise HostError("Token creation requires a secure output pipe")
    # Never accept operator identity/DSN overrides from the caller or ambient environment.
    return command([config["node"], _software(config) / "runtime/team-memory-operator.mjs", *argv],
                   env=dict(_database_env(config, credential(config, "operator", keychain)),
                            MEMORY_OPERATOR_USER_ID=config["owner_id"]),
                   capture=False, check=False).returncode
