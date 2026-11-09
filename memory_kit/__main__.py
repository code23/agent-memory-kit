"""Human management CLI. Never print config, credentials or driver exceptions."""
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True

from . import host
from .client import ClientError
from .keychain import SecretStoreError
from .security import SecurityError


def parser():
    root = argparse.ArgumentParser(prog="memory-kit")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("doctor", "plan", "install"):
        command = commands.add_parser(name)
        command.add_argument("--workspace", required=True)
        command.add_argument("--coding-user", required=True)
        command.add_argument("--root", type=Path)
        command.add_argument("--pg-bin", type=Path)
        command.add_argument("--node", type=Path)
    for name in ("start", "status", "stop", "uninstall", "daemon", "operator"):
        command = commands.add_parser(name)
        command.add_argument("--root", required=True, type=Path)
        if name == "operator":
            command.add_argument("args", nargs=argparse.REMAINDER)
    for name in ("connect", "reconnect", "connect-check"):
        connect = commands.add_parser(name)
        connect.add_argument("--project", required=True, type=Path)
        connect.add_argument("--workspace", required=True)
        connect.add_argument("--url", required=True)
        connect.add_argument("--instance", required=True)
        connect.add_argument("--native-argv", type=json.loads)
        if name == "connect-check":
            connect.add_argument("--expected-uid", required=True, type=int)
            connect.add_argument("--rekey", action="store_true")
            connect.add_argument("--review-context", action="store_true")
    run = commands.add_parser("run")
    run.add_argument("--profile", required=True, type=Path)
    run.add_argument("args", nargs=argparse.REMAINDER)
    return root


def main(argv=None):
    if sys.version_info < (3, 11):
        print("Python 3.11 or newer is required; install prerequisites separately.", file=sys.stderr)
        return 1
    args = parser().parse_args(argv)
    try:
        if args.command in ("connect", "reconnect", "connect-check", "run"):
            from . import client
            from .keychain import MacKeychain
            if args.command == "connect-check":
                result = client.check_connection(args.project, args.workspace, args.url,
                                                 MacKeychain(), args.instance, args.expected_uid,
                                                 rekey=args.rekey, native_argv=args.native_argv,
                                                 review_context=args.review_context)
            elif args.command in ("connect", "reconnect"):
                if sys.stdin.isatty():
                    raise host.HostError("Provide the agent credential through a secure input pipe")
                # Current context authority is checked before accepting credential input.
                from . import context_authority
                project = client._project(args.project)
                if args.native_argv is None:
                    with context_authority._early_reads(project):
                        client._check_logthis(project)
                with context_authority.decision(project, args.workspace, args.url,
                                                args.instance, args.native_argv):
                    pass
                token = sys.stdin.buffer.read(4097).strip()
                if not token or len(token) > 4096:
                    raise host.HostError("Agent credential input is invalid")
                getattr(client, args.command)(args.project, args.workspace, args.url, token,
                                              MacKeychain(), args.instance, native_argv=args.native_argv)
                result = {"connected": True}
            else:
                native_args = args.args[1:] if args.args[:1] == ["--"] else args.args
                return client.run(args.profile, native_args, MacKeychain())
        elif args.command in ("doctor", "plan", "install"):
            preflight = host.plan(args.workspace, args.coding_user, args.root,
                                  args.pg_bin, args.node)
            if args.command == "install":
                result = host.install(preflight)
            else:
                result = {"ready": True, "workspace": preflight["workspace"],
                          "existing_installation": preflight["existing"] is not None,
                          "postgres_port": host.PG_PORT, "service_port": host.SERVICE_PORT,
                          "changes_made": False}
        else:
            if args.command == "operator":
                runtime_args = args.args[1:] if args.args[:1] == ["--"] else args.args
                if runtime_args in (["context", "approve"], ["context", "revoke"]):
                    from . import context_authority
                    packet = b'{}' if runtime_args[-1]=='revoke' else sys.stdin.buffer.read(context_authority.MAX_PACKET + 1)
                    if len(packet) > context_authority.MAX_PACKET:
                        raise ClientError("Context review packet is too large.")
                    result = context_authority.operator(None if runtime_args[-1]=='revoke' else context_authority.parse(packet),
                                                        revoke=runtime_args[-1] == "revoke")
                    print(json.dumps(result, sort_keys=True))
                    return 0
            config = host.load(args.root, runtime=args.command not in ("stop", "status", "uninstall"))
            if args.command == "operator":
                runtime_args = args.args[1:] if args.args[:1] == ["--"] else args.args
                return host.operator(config, runtime_args)
            if args.command == "daemon":
                return host.daemon(config)
            result = getattr(host, args.command)(config)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (host.HostError, SecurityError, SecretStoreError, ClientError) as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError, KeyError):
        print("Local operation failed safely; inspect installation prerequisites", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
