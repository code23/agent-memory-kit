"""Observed LOCAL context interlock for a conservative Claude Code release subset.

The fixed discovery anchor must be bootstrapped separately by a host operator.
There is deliberately no environment/profile override or development bypass.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import sys
import time

from . import security

DISCOVERY = Path('/Library/Application Support/Agent Memory Kit/Context Authority')
SUPPORTED_CONTRACTS = frozenset({'claude-code/2.1.318', 'claude-code/2.1.319'})
MAX_PACKET = 4 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def fail(message):
    from .client import ClientError
    raise ClientError(message)


def parse(data):
    from .client import _json
    try:
        value = _json(data)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, TypeError, UnicodeError):
        fail('Context authority metadata is malformed.')


def read_at(fd, name, uid):
    data, opened, _ = security.public_file_at(fd, name, uid)
    os.close(opened)
    return data


def identity(uid):
    import pwd
    return security.standard_coding_identity(pwd.getpwuid(uid).pw_name)


@contextmanager
def authority(coding_uid=None):
    """Resolve the root-owned delegation and protected software files on disk."""
    # Discovery is rooted in root custody, independent of packet/environment.
    probe={'uid':os.getuid()}
    with security.public_directory(DISCOVERY, 0, probe) as fd:
        delegation = parse(read_at(fd, 'authority.json', 0))
    if (set(delegation) != {'version', 'operator_uid', 'coding_uid', 'root'} or type(delegation['version']) is not int or delegation['version'] != 1
            or type(delegation['operator_uid']) is not int
            or type(delegation['coding_uid']) is not int or delegation['coding_uid'] < 501
            or delegation['operator_uid'] < 501 or delegation['operator_uid'] == delegation['coding_uid']
            or coding_uid is not None and coding_uid != delegation['coding_uid']
            or not isinstance(delegation['root'], str)):
        fail('Context authority delegation is invalid.')
    coding=identity(delegation['coding_uid'])
    root, uid = Path(delegation['root']), delegation['operator_uid']
    software = root / 'software'
    running = Path(__file__).absolute().parent.parent
    if running != software:
        fail('Lifecycle commands require the protected delegated software copy.')
    security.assert_not_agent_writable(software, coding)
    from .host import _source_files
    observed = []
    for path in _source_files(software):
        with security.public_directory(path.parent, uid, coding) as parent:
            observed.append([str(path.relative_to(software)), digest(read_at(parent, path.name, uid))])
    with security.public_directory(root, uid, coding) as directory:
        yield directory, uid, digest(canonical(observed))


EXCLUDED = ('remote policy fetch', 'runtime MCP instructions', 'hook output',
            'auto-update', 'remote plugin marketplaces')
SETTINGS = {'model', 'permissions', 'autoMemoryEnabled'}
INACTIVE_AUTO_MEMORY = 'auto-memory-disabled/v1'
SOURCE_FILES = ('CLAUDE.md', 'CLAUDE.local.md', 'AGENTS.md', '.claude/CLAUDE.md',
                '.claude/AGENTS.md', '.claude/settings.json', '.claude/settings.local.json', '.mcp.json')
SOURCE_TREES = ('rules', 'skills', 'commands', 'agents', 'prompts')


# Conservative observed key-name inventory, 2026-11-09; sources and exclusions
# are documented in docs/mac-installation-plan.md. No account values are exported.
INERT_STATE_KEYS = frozenset({
    'userID', 'anonymousId', 'machineID', 'oauthAccount', 'numStartups',
    'firstStartTime', 'installMethod', 'migrationVersion', 'lastOnboardingVersion',
    'hasCompletedOnboarding', 'hasIdeOnboardingBeenShown', 'hasUsedBackslashReturn',
    'shiftEnterKeyBindingInstalled', 'lastReleaseNotesSeen', 'changelogLastFetched',
    'announcementImpressions', 'seenNotifications', 'tipsHistory', 'tipsHistoryByCommand',
    'tipLifetimeShownCounts', 'feedbackSurveyState', 'lastShownEmergencyTip',
    'ideHintShownCount', 'subscriptionNoticeCount', 'birthdayHatAnimationCount',
    'btwUseCount', 'promptQueueUseCount', 'hasSeenStashHint', 'hasSeenTasksHint',
    'hasUsedStash', 'effortCalloutDismissed', 'effortCalloutV2Dismissed',
    'hasSeenEffortMediumNudgeByModel', 'diffSidebarOpen', 'showSpinnerTree',
    'lastClawdEntranceVersion', 'claudeCodeFirstTokenDate',
})
INERT_PROJECT_STATE_KEYS = frozenset({
    'lastCost', 'lastDuration', 'lastAPIDuration', 'lastAPIDurationWithoutRetries',
    'lastToolDuration', 'lastLinesAdded', 'lastLinesRemoved', 'lastTotalInputTokens',
    'lastTotalOutputTokens', 'lastTotalCacheCreationInputTokens',
    'lastTotalCacheReadInputTokens', 'lastTotalWebSearchRequests', 'lastModelUsage',
    'lastFpsAverage', 'lastFpsLow1Pct', 'lastSessionId', 'lastSessionMetrics',
    'lastSessionModified', 'lastStartTime', 'lastGracefulShutdown', 'lastVersionBase',
})
CONTEXT_STATE_KEYS = frozenset({
    'mcpServers', 'mcpContextUris', 'enabledMcpjsonServers', 'disabledMcpjsonServers',
    'enabledMcpServers', 'disabledMcpServers', 'enableAllProjectMcpServers',
    'allowedMcpServers', 'deniedMcpServers', 'managedMcpServers',
    'hasTrustDialogAccepted', 'hasTrustDialogHooksAccepted',
    'hasClaudeMdExternalIncludesApproved', 'hasClaudeMdExternalIncludesWarningShown',
    'allowedTools', 'ignorePatterns', 'exampleFiles', 'exampleFilesGeneratedAt',
    'hooks', 'env', 'permissions', 'autoMemoryEnabled', 'autoMemoryDirectory',
    'model', 'additionalDirectories', 'enabledPlugins', 'extraKnownMarketplaces',
    'autoConnectIde', 'autoInstallIdeExtension', 'claudeInChromeDefaultEnabled',
    'chromeExtension', 'autoUpdates', 'autoUpdatesProtectedForNative',
    'remoteControlSpawnMode', 'defaultToAgentsView', 'externalEditorContext',
})
INERT_STATE = {'excluded': 'inert-claude-state', 'classification': 'keys/v1'}
EMPTY_STATE_KEYS = {
    'allowedTools': list, 'mcpServers': dict, 'mcpContextUris': list,
    'enabledMcpjsonServers': list, 'disabledMcpjsonServers': list,
    'enabledMcpServers': list, 'disabledMcpServers': list,
    'ignorePatterns': list, 'exampleFiles': list,
}
BOOLEAN_STATE_KEYS = frozenset({
    'hasTrustDialogAccepted', 'hasTrustDialogHooksAccepted',
    'hasClaudeMdExternalIncludesApproved', 'hasClaudeMdExternalIncludesWarningShown',
    'bypassPermissionsModeAccepted',
})


def _classify_state(value):
    """Fail closed at each loader scope; inert account/metrics values stay local.

    Every project entry is classified, not only the launch folder's: Claude Code keys
    project state by the git root (or folder) it resolves, so an ancestor or
    differently-cased key can carry context for this launch."""
    def check_keys(mapping, allowed):
        if not isinstance(mapping, dict): fail('Malformed Claude Code state scope.')
        for key in set(mapping) & EMPTY_STATE_KEYS.keys():
            if type(mapping[key]) is not EMPTY_STATE_KEYS[key] or mapping[key]:
                fail('Context-affecting Claude Code state is unsupported.')
        for key in set(mapping) & BOOLEAN_STATE_KEYS:
            if type(mapping[key]) is not bool:
                fail('Malformed Claude Code acceptance flag.')
        classified = EMPTY_STATE_KEYS.keys() | BOOLEAN_STATE_KEYS
        if set(mapping) & (CONTEXT_STATE_KEYS - classified):
            fail('Context-affecting Claude Code state is unsupported.')
        if set(mapping) - allowed - classified:
            fail('Unknown Claude Code state key is unsupported.')
    check_keys(value, INERT_STATE_KEYS | {'projects'})
    projects = value.get('projects', {})
    if not isinstance(projects, dict): fail('Malformed Claude Code project state.')
    for entry in projects.values():
        check_keys(entry, INERT_PROJECT_STATE_KEYS)
    return dict(INERT_STATE)


def _roots():
    from .client import _home
    home = _home()
    if os.environ.get('HOME',str(home))!=str(home):
        fail('An alternate HOME selector is unsupported; keep the native account home.')
    selector = os.environ.get('CLAUDE_CONFIG_DIR', str(home / '.claude'))
    config = Path(selector)
    if not config.is_absolute() or config != Path(os.path.abspath(config)):
        fail('Native configuration selector must be an absolute canonical path.')
    import pwd
    name=pwd.getpwuid(os.getuid()).pw_name
    return home, config, Path('/Library/Application Support/ClaudeCode'), (
        Path('/Library/Managed Preferences/com.anthropic.claudecode.plist'),
        Path('/Library/Managed Preferences') / name / 'com.anthropic.claudecode.plist',
        home / 'Library/Managed Preferences/com.anthropic.claudecode.plist',
        home / 'Library/Preferences/com.anthropic.claudecode.plist')


def _native(argv):
    """Observe exact native release identity without invoking the client."""
    import shutil
    if not isinstance(argv, list) or not argv or any(not isinstance(x,str) or not x or '\x00' in x for x in argv):
        fail('Native Claude Code argv is required; supply native Claude command arguments.')
    selected = shutil.which(argv[0])
    if not selected:
        fail('Claude executable is unavailable.')
    path = Path(selected).resolve(strict=True)
    if 'claude-code/'+path.name not in SUPPORTED_CONTRACTS or path.parent.name != 'versions':
        fail('Unsupported Claude Code native release layout; only versions/2.1.318 and versions/2.1.319 are supported.')
    for candidate in (path,) + tuple(path.parents):
        info = candidate.lstat()
        if info.st_uid not in (0, os.getuid()) or info.st_mode & 0o022:
            fail('Native executable or ancestor custody is unsafe.')
    from .client import _directory
    with _directory(path.parent) as fd:
        security._check_acl(fd)
        opened = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            security._check_acl(opened)
            before = os.fstat(opened)
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                    or before.st_uid not in (0, os.getuid()) or before.st_mode & 0o022):
                fail('Native executable identity is unsafe.')
            h = hashlib.sha256()
            magic = os.read(opened,4)
            if magic not in (b'\xcf\xfa\xed\xfe',b'\xca\xfe\xba\xbe'):
                fail('Unsupported native executable format.')
            h.update(magic)
            marker=f'README_URL:"https://code.claude.com/docs/en/overview",VERSION:"{path.name}"'.encode()
            release_seen=False;tail=b''
            while True:
                chunk=os.read(opened,1024*1024)
                if not chunk:break
                h.update(chunk)
                release_seen=release_seen or marker in tail+chunk
                tail=chunk[-len(marker):]
            if not release_seen:fail(f'Native embedded release metadata does not match {path.name}.')
            after=os.fstat(opened)
            named=os.stat(path.name,dir_fd=fd,follow_symlinks=False)
            if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) or (before.st_dev,before.st_ino)!=(named.st_dev,named.st_ino):
                fail('Native executable changed while observed.')
        finally:os.close(opened)
    return {'path':str(path),'version':path.name,'sha256':h.hexdigest()}


def _environment():
    # Only context selectors enter approval. Authentication is inherited privately.
    allowed = {'HOME','CLAUDE_CONFIG_DIR','CODEX_HOME','PATH','ANTHROPIC_MODEL',
               'ANTHROPIC_DEFAULT_MODEL','ANTHROPIC_DEFAULT_OPUS_MODEL',
               'ANTHROPIC_DEFAULT_SONNET_MODEL','ANTHROPIC_DEFAULT_HAIKU_MODEL'}
    credentials = {'ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','CLAUDE_CODE_OAUTH_TOKEN'}
    for key in os.environ:
        if ((key.startswith(('CLAUDE_','ANTHROPIC_','GIT_','NODE_','BUN_','PYTHON'))
             or key.startswith(('DYLD_','LD_','XDG_')) or key in ('BASH_ENV','ENV','ZDOTDIR')) and key not in allowed | credentials):
            fail('Unknown native context or injection environment selector.')
    return {key:os.environ[key] for key in sorted(allowed) if key in os.environ}


def _arguments(argv):
    if not isinstance(argv, list) or not argv or any(not isinstance(x,str) or not x or '\x00' in x for x in argv):
        fail('Native Claude Code argv is required; supply native Claude command arguments.')
    index=1
    while index<len(argv):
        value=argv[index]
        if value in ('--model','--permission-mode'):
            if index+1>=len(argv) or not argv[index+1] or argv[index+1].startswith('-'):
                fail('Native argument value is missing.')
            if value=='--permission-mode' and argv[index+1] not in ('bypassPermissions','default','acceptEdits','plan'):
                fail('Unsupported permission mode.')
            index+=2
        elif value in ('--dangerously-skip-permissions',):index+=1
        else:fail('Unknown or unsupported context-affecting native argument.')


def _read(path):
    """Bounded local source read; distinct from private/project mutation guards."""
    from .client import _directory, _planned_path, _planned_at
    path=Path(path)
    if not path.is_absolute():fail('Context source path must be absolute.')
    try:
        info=path.lstat()
    except FileNotFoundError:
        _planned_path(path, None)
        return None
    _planned_path(path, info)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_mode&0o022 or info.st_size>1024*1024:
        fail('Unsupported context source type, link, size or permissions.')
    with _directory(path.parent) as parent:
        opened=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
        try:
            before=os.fstat(opened)
            _planned_at(parent, path.name, before)
            if (before.st_dev,before.st_ino)!=(info.st_dev,info.st_ino):fail('Context source replaced.')
            data=b''
            while len(data)<=1024*1024:
                chunk=os.read(opened,65536)
                if not chunk:break
                data+=chunk
            after=os.fstat(opened)
            named=os.stat(path.name,dir_fd=parent,follow_symlinks=False)
            if len(data)>1024*1024 or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns) or (before.st_dev,before.st_ino)!=(named.st_dev,named.st_ino):fail('Context source changed while observed.')
            with _directory(path.parent) as checked_parent:
                first_parent=os.fstat(parent);last_parent=os.fstat(checked_parent)
                if (first_parent.st_dev,first_parent.st_ino)!=(last_parent.st_dev,last_parent.st_ino):fail('Context source parent replaced.')
            return data
        finally:os.close(opened)


def _classified(path, kind='markdown', project=None):
    data=_read(path)
    if data is None:return None
    try:text=data.decode('utf-8')
    except UnicodeError:fail('Unsupported non-UTF8 context source.')
    if kind=='settings':
        value=parse(text)
        if set(value)-SETTINGS:fail('Unknown settings, plugin, hook or import mechanism.')
        if 'autoMemoryEnabled' in value and type(value['autoMemoryEnabled']) is not bool:fail('Invalid auto-memory setting.')
        if 'model' in value and not isinstance(value['model'],str):fail('Invalid native model setting.')
        if 'permissions' in value and value['permissions'] not in ({},{'defaultMode':'bypassPermissions'}):fail('Unsupported permission settings mechanism.')
    elif kind=='state':
        return _classify_state(parse(text))
    elif kind=='empty':
        if parse(text)!={}:fail('Nonempty managed policy/global configuration is unsupported.')
    elif kind=='mcp':
        from .client import SERVER_NAME,TOKEN_ENV
        value=parse(text)
        if set(value)-{'mcpServers'} or not isinstance(value.get('mcpServers',{}),dict):fail('Unsupported MCP configuration.')
        for name,server in value.get('mcpServers',{}).items():
            if (name!=SERVER_NAME or not isinstance(server,dict) or set(server)!={'type','url','headers'}
                    or server['type']!='http' or server['headers']!={'Authorization':'Bearer ${'+TOKEN_ENV+'}'}):
                fail('Unclassified MCP source or credentials are unsupported.')
    else:
        # Refuse all imports and frontmatter: no partial Markdown/YAML parser.
        if '@' in text or text.startswith('---') or '!`' in text:
            fail('Instruction imports, frontmatter or dynamic command input are unsupported.')
    return {'text':text,'sha256':digest(data)}


def _path_metadata(path):
    from .client import _directory
    path = Path(path)
    chain = []
    leaf = None
    existing = Path('/')
    for item in reversed((path,) + tuple(path.parents)):
        try: info = item.lstat()
        except FileNotFoundError: continue
        if stat.S_ISLNK(info.st_mode): fail('Linked source namespace is unsupported.')
        if item != path and not stat.S_ISDIR(info.st_mode): fail('Invalid source ancestor type.')
        chain.append((str(item), info.st_dev, info.st_ino, info.st_mode))
        if item != path and stat.S_ISDIR(info.st_mode): existing = item
        if item == path:
            leaf = (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns)
    with _directory(existing) as fd:
        opened = os.fstat(fd)
        named = existing.lstat()
        if (opened.st_dev,opened.st_ino)!=(named.st_dev,named.st_ino): fail('Source namespace replaced.')
    return leaf, tuple(chain)


def _remember_metadata(path, metadata):
    path = Path(path)
    value = _path_metadata(path)
    private = metadata['private']
    if path != private:
        if private in path.parents:
            fail('Active source overlaps private memory namespace.')
        private_value = metadata['paths'].get(str(private))
        if private_value and private_value[0] is not None:
            private_id = private_value[0][:2]
            if any((entry[1],entry[2]) == private_id for entry in value[1]):
                fail('Active source aliases private memory namespace.')
    if str(path) in metadata['paths'] and metadata['paths'][str(path)] != value:
        fail('Source metadata changed during discovery.')
    metadata['paths'][str(path)] = value
    dirs = metadata.setdefault('dirs', {})
    for name, device, inode, mode in value[1]:
        if stat.S_ISDIR(mode):
            if name in dirs and dirs[name] != (device, inode): fail('Planned directory changed.')
            dirs[name] = (device, inode)
    metadata.setdefault('leaves', {})[str(path)] = value[0]
    parent_id = dirs.get(str(path.parent))
    if parent_id is not None:
        metadata.setdefault('at', {})[(*parent_id, path.name)] = value[0]
    return value


def _admit_source_roots(project, config, managed, scopes):
    private = config/'projects'
    metadata = {'private': private, 'paths': {}}
    info = _remember_metadata(private,metadata)[0]
    if info is not None and not stat.S_ISDIR(info[2]): fail('Invalid private memory root type.')
    for container in (project, config, managed) + tuple(root/'.claude' for root in scopes):
        value = _remember_metadata(container,metadata)[0]
        if value is not None and not stat.S_ISDIR(value[2]): fail('Invalid source container type.')
    roots = [project, project/'.codex', managed/'managed-settings.d', managed/'plugins',
             config/'plugins', config/'agent-memory']
    roots += [root/'.claude'/'plugins' for root in scopes]
    roots += [root/name for root in (managed,config) for name in SOURCE_TREES]
    roots += [root/'.claude'/name for root in scopes for name in SOURCE_TREES]
    for root in roots:
        if root == private or root in private.parents or private in root.parents:
            fail('Recursive source and private memory namespaces overlap.')
        value = _remember_metadata(root,metadata)
        if value[0] is not None and not stat.S_ISDIR(value[0][2]): fail('Invalid recursive source type.')
        if value[0] is not None and any((x[1],x[2]) == value[0][:2] for x in metadata['paths'][str(private)][1]):
            fail('Recursive source contains private memory namespace.')
    return metadata


def _plan_empty(path, inventory, metadata):
    _remember_metadata(path,metadata)
    _absent_or_empty(path,inventory,metadata)


def _plan_project(root, inventory, metadata):
    _remember_metadata(root/'.claude',metadata)
    _project_claude(root,inventory,metadata)


def _plan_slot(slots, metadata, path, kind='markdown'):
    value = _remember_metadata(path,metadata)[0]
    if value is not None and (not stat.S_ISREG(value[2]) or value[3] > 1024*1024):
        fail('Unsupported source slot type or size.')
    slots[str(path)] = kind
    return None


def _check_plan(metadata):
    for path, expected in metadata['paths'].items():
        if _path_metadata(path) != expected: fail('Source metadata changed after discovery.')


@contextmanager
def _listed_directory(path, metadata):
    from . import client
    path = Path(path)
    if path == metadata['private'] or metadata['private'] in path.parents:
        fail('Private memory cannot be enumerated.')
    try:
        with client._planned_io(metadata), client._directory(path) as descriptor:
            expected = metadata['paths'][str(path)][0]
            opened = os.fstat(descriptor)
            if expected is None or expected[:2] != (opened.st_dev, opened.st_ino):
                fail('Listing directory differs from its plan.')
            with os.scandir(descriptor) as entries:
                # Names/stat belong to this still-open directory, never a new path.
                yield descriptor, sorted((entry.name, entry.stat(follow_symlinks=False)) for entry in entries)
    except FileNotFoundError:
        fail('Planned source directory disappeared during inventory.')


@contextmanager
def _early_reads(project):
    from . import client
    _, _, metadata, _ = _plan_sources(project)
    with client._planned_io(metadata):
        yield


def _project_directories(project, metadata):
    pending = [project]
    while pending:
        root = pending.pop()
        _remember_metadata(root,metadata)
        yield root
        with _listed_directory(root, metadata) as (_, children):
            for name, info in children:
                if name in ('.git','.claude','.codex'): continue
                child = root / name
                if stat.S_ISLNK(info.st_mode): fail('Descendant source links are unsupported.')
                if stat.S_ISDIR(info.st_mode):
                    _remember_metadata(child,metadata)
                    pending.append(child)


def _tree(path,inventory,slots,metadata):
    path=Path(path)
    info = _remember_metadata(path, metadata)[0]
    if info is None:
        inventory[str(path)]=None;return
    if not stat.S_ISDIR(info[2]) or info[2]&0o022:fail('Unsupported context tree or symlink.')
    inventory[str(path)]={'directory':True}
    before=(info[0],info[1],info[4])
    with _listed_directory(path, metadata) as (_, children):
        for name, child_info in children:
            child = path / name
            if stat.S_ISLNK(child_info.st_mode):fail('Context tree symlinks are unsupported.')
            if stat.S_ISDIR(child_info.st_mode):_tree(child,inventory,slots,metadata)
            elif child.suffix in ('.md','.txt'):
                inventory[str(child)]=_plan_slot(slots,metadata,child)
            else:fail('Unknown skill/command/agent/rule support file or credentials.')
    after=path.lstat()
    if before!=(after.st_dev,after.st_ino,after.st_mtime_ns):fail('Context tree changed during inventory.')


def _absent_or_empty(path,inventory,metadata):
    path=Path(path)
    info = metadata['paths'][str(path)][0]
    if info is None:inventory[str(path)]=None;return
    if not stat.S_ISDIR(info[2]):fail('Nonempty or linked plugin/managed source is unsupported.')
    with _listed_directory(path,metadata) as (_, children):
        if children: fail('Nonempty plugin/managed source is unsupported.')
    inventory[str(path)]={'directory':True}


def _project_claude(root, inventory,metadata):
    directory=root/'.claude'
    info = metadata['paths'][str(directory)][0]
    if info is None:
        inventory[str(directory)]=None;return
    if not stat.S_ISDIR(info[2]):fail('Linked project configuration directories are unsupported.')
    allowed=set(SOURCE_TREES)|{'plugins','CLAUDE.md','CLAUDE.local.md','AGENTS.md','settings.json','settings.local.json'}
    with _listed_directory(directory,metadata) as (_, children):
        if any(name not in allowed for name, _ in children):
            fail('Unknown project-local loading source.')
    inventory[str(directory)]={'directory':True}


def _scope_roots(project):
    return (project,)+tuple(project.parents)


def _require_auto_memory_disabled(inventory, user_settings):
    values = []
    selected_user_policy = None
    for path, entry in inventory.items():
        if (isinstance(entry, dict) and 'text' in entry
                and path.endswith(('settings.json', 'settings.local.json'))):
            value = parse(entry['text'])
            if 'autoMemoryEnabled' in value:
                values.append(value['autoMemoryEnabled'])
                if path == str(user_settings):
                    selected_user_policy = value['autoMemoryEnabled']
    if selected_user_policy is not False or not values or any(type(value) is not bool or value is not False for value in values):
        fail('This subset requires already-observed autoMemoryEnabled=false; it never changes native settings.')


def _inactive_memory_root(identity):
    """Derive the sole eligible inactive slot, never caller-selected sources."""
    environment = identity['environment']
    if 'HOME' in environment:
        home = environment['HOME']
    else:
        import pwd
        try:
            home = pwd.getpwuid(identity['coding_uid']).pw_dir
        except (KeyError, TypeError, OverflowError):
            fail('Cannot resolve the coding account memory root.')
    config = Path(environment.get('CLAUDE_CONFIG_DIR', str(Path(home) / '.claude')))
    if not config.is_absolute() or config != Path(os.path.abspath(config)):
        fail('Invalid native memory root selector.')
    return str(config / 'projects')


def _validate_namespaces(project, config):
    """Validate recorded path spelling without opening coder-owned folders."""
    project, config = Path(project), Path(config)
    if any(not path.is_absolute() or path != Path(os.path.abspath(path)) for path in (project, config)):
        fail('Project and native configuration need canonical absolute namespaces.')
    if config == project or project in config.parents:
        fail('Native configuration inside the project namespace is unsupported.')
    return project, config


def _admit_native_namespace(project, config):
    """Coder-side alias checks before any context intake."""
    from .client import _directory
    project, config = _validate_namespaces(project, config)
    try:
        with _directory(project) as fd:
            info = os.fstat(fd)
            project_identity = (info.st_dev, info.st_ino)
        # No-follow opens reject linked ancestors. Inode comparison also covers
        # alternate spellings on case-insensitive filesystems, without bodies.
        for ancestor in (config,) + tuple(config.parents):
            with _directory(ancestor) as fd:
                info = os.fstat(fd)
                if (info.st_dev, info.st_ino) == project_identity:
                    fail('Native configuration overlaps the canonical project namespace.')
    except OSError:
        fail('Linked or unavailable native configuration namespace is unsupported.')


def _plan_sources(project):
    """Observe this supported local subset; native coverage remains unqualified."""
    from . import client
    home,config,managed,preferences=_roots()
    _admit_native_namespace(project, config)
    inventory={}
    metadata = _admit_source_roots(project, config, managed, _scope_roots(project))
    slots = {}
    # No git redirection or linked worktree: those loading paths are unsupported.
    if os.path.lexists(project/'.git') and (project/'.git').is_symlink():fail('Linked git metadata is unsupported.')
    if (project/'.git').is_file():fail('Linked worktree/gitfile loading is unsupported.')
    for path in preferences:
        if _remember_metadata(path,metadata)[0] is not None:fail('Managed native preferences require a classified observer; this subset refuses them.')
        inventory[str(path)]=None
    for name in ('managed-settings.json','managed-mcp.json'):
        inventory[str(managed/name)]=_plan_slot(slots, metadata, managed/name,'empty')
    _plan_empty(managed/'managed-settings.d',inventory,metadata)
    inventory[str(managed/'CLAUDE.md')]=_plan_slot(slots, metadata, managed/'CLAUDE.md')
    for name in SOURCE_TREES:_tree(managed/name,inventory,slots,metadata)
    _plan_empty(managed/'plugins',inventory,metadata)
    for name,kind in (('CLAUDE.md','markdown'),('CLAUDE.local.md','markdown'),('AGENTS.md','markdown'),('settings.json','settings'),
                      ('settings.local.json','settings'),('remote-settings.json','empty'),
                      ('policy-limits.json','empty')):
        inventory[str(config/name)]=_plan_slot(slots, metadata, config/name,kind)
    for name in ('remote-settings.json.signature.json','remote-settings.json.signature-iat.json',
                 'policy-limits.json.signature.json','policy-limits.json.signature-iat.json'):
        # Cache metadata unclassified in this subset: refuse active instead of skipping.
        if os.path.lexists(config/name):fail('Signed remote cache metadata is unsupported by this subset.')
        inventory[str(config/name)]=None
    # The global mixed account/configuration file cannot silently hide local MCP.
    inventory[str(home/'.claude.json')]=_plan_slot(slots, metadata, home/'.claude.json','state')
    inventory[str(config/'.claude.json')]=_plan_slot(slots, metadata, config/'.claude.json','state')
    if config!=home/'.claude':inventory[str(config.with_suffix('.json'))]=_plan_slot(slots, metadata, config.with_suffix('.json'),'state')
    for name in SOURCE_TREES:_tree(config/name,inventory,slots,metadata)
    _plan_empty(config/'plugins',inventory,metadata)
    _plan_empty(config/'agent-memory',inventory,metadata)
    for credential in (config/'.credentials.json',):
        present = _remember_metadata(credential,metadata)[0] is not None
        inventory[str(credential)]={'excluded':'credentials','present':present}
    codex=project/'.codex'
    if metadata['paths'][str(codex)][0] is not None:
        with _listed_directory(codex,metadata) as (_, children):
            if any(name!='config.toml' for name, _ in children): fail('Unsupported nested Codex configuration discovery.')
    scopes=_scope_roots(project)
    for root in scopes:
        if root/'.claude' != config:
            _plan_project(root,inventory,metadata)
        if (root/'.git').is_file() or (root/'.git').is_symlink():fail('Linked ancestor git/worktree source is unsupported.')
        if root!=project and os.path.lexists(root/client.PROFILE_NAME):fail('Ancestor business binding is unsupported.')
        for name in SOURCE_FILES:
            path=root/name
            kind='settings' if name.endswith(('settings.json','settings.local.json')) else 'mcp' if name=='.mcp.json' else 'markdown'
            inventory[str(path)]=_plan_slot(slots, metadata, path,kind)
        for name in SOURCE_TREES:_tree(root/'.claude'/name,inventory,slots,metadata)
        _plan_empty(root/'.claude/plugins',inventory,metadata)
    # Descendant instruction/config sources may load later. Inventory every
    # directory's discovery slots, without reading unrelated project bodies.
    for root in _project_directories(project, metadata):
        if Path(root)==project:continue
        _plan_project(Path(root),inventory,metadata)
        for name in SOURCE_FILES:
            kind='settings' if name.endswith(('settings.json','settings.local.json')) else 'mcp' if name=='.mcp.json' else 'markdown'
            inventory[str(Path(root)/name)]=_plan_slot(slots, metadata, Path(root)/name,kind)
        for name in SOURCE_TREES:_tree(Path(root)/'.claude'/name,inventory,slots,metadata)
        _plan_empty(Path(root)/'.claude/plugins',inventory,metadata)
    for name in client._FILES:
        if str(project/name) not in slots:
            inventory[str(project/name)] = _plan_slot(slots, metadata, project/name)
    _plan_slot(slots, metadata, project/client.PROFILE_NAME, None)
    _check_plan(metadata)
    return inventory, slots, metadata, config


def observe(project, workspace, url, instance, argv, software_digest):
    from . import client
    inventory, slots, metadata, config = _plan_sources(project)
    native = _native(argv)
    _arguments(argv)
    environment = _environment()
    with client._planned_io(metadata):
        # All roots and source slots are now known and admitted; only now read bodies.
        _check_plan(metadata)
        for path, kind in slots.items():
            if kind is not None:
                inventory[path] = (_classified(Path(path), kind, project=project) if kind == 'state'
                                   else _classified(Path(path), kind))
        _require_auto_memory_disabled(inventory, config / 'settings.json')
        projects = config / 'projects'
        inventory[str(projects)] = {'inactive': INACTIVE_AUTO_MEMORY,
                                    'present': metadata['paths'][str(projects)][0] is not None}
        if client._snapshot(project/client.PROFILE_NAME) is None:
            _,_,outputs,_=client._prepare_binding(project,workspace,url,instance)
        else:
            loaded=client._load_profile(project/client.PROFILE_NAME)
            if (loaded['workspace'],loaded['url'])!=(workspace,url):fail('Context workspace/service changed.')
            outputs=client._verify(project,loaded)
        current=dict(inventory);prospective=dict(inventory)
        for name in client._FILES:
            prospective[str(project/name)]={'text':outputs[name].decode(),'sha256':digest(outputs[name])}
        _check_plan(metadata)
        info=metadata['paths'][str(project)][0]
        return {'version':1,'contract':'claude-code/'+native['version'],'excluded':list(EXCLUDED),
                'identity':{'coding_uid':os.getuid(),'project':str(project),'device':info[0],'inode':info[1],
                            'workspace':workspace,'url':url,'argv':argv,'environment':environment,
                            'software':software_digest,'executable':native},
                'current':current,'prospective':prospective}


def hashes(value):
    if isinstance(value, dict):
        return {key: hashes(item) for key, item in value.items() if key != 'text'}
    if isinstance(value, list):
        return [hashes(item) for item in value]
    return value


def validate_packet(packet):
    if (not isinstance(packet,dict) or set(packet)!={'version','contract','excluded','identity','current','prospective'}
            or packet['version']!=1 or not isinstance(packet['contract'], str) or packet['contract'] not in SUPPORTED_CONTRACTS
            or packet['excluded']!=list(EXCLUDED) or not isinstance(packet['identity'],dict)
            or set(packet['identity'])!={'coding_uid','project','device','inode','workspace','url','argv','environment','software','executable'}
            or type(packet['identity']['coding_uid']) is not int
            or not isinstance(packet['identity']['environment'],dict)):
        fail('Invalid native context review packet.')
    if any(key not in {'HOME','CLAUDE_CONFIG_DIR','CODEX_HOME','PATH','ANTHROPIC_MODEL','ANTHROPIC_DEFAULT_MODEL','ANTHROPIC_DEFAULT_OPUS_MODEL','ANTHROPIC_DEFAULT_SONNET_MODEL','ANTHROPIC_DEFAULT_HAIKU_MODEL'} or not isinstance(value,str) or '\x00' in value for key,value in packet['identity']['environment'].items()):
        fail('Review packet contains unclassified environment or credentials.')
    # The operator validates recorded identity only; the coding user's decision()
    # observes the current executable again before authorising launch.
    native = packet['identity']['executable']
    if (not isinstance(native,dict) or set(native)!={'path','version','sha256'}
            or not isinstance(native['version'],str)
            or 'claude-code/'+native['version'] not in SUPPORTED_CONTRACTS
            or not isinstance(native['path'],str) or not Path(native['path']).is_absolute()
            or Path(native['path']) != Path(os.path.abspath(native['path']))
            or Path(native['path']).name!=native['version']
            or Path(native['path']).parent.name!='versions'
            or not isinstance(native['sha256'],str) or len(native['sha256'])!=64
            or any(char not in '0123456789abcdef' for char in native['sha256'])
            or packet['contract'] != 'claude-code/'+native['version']):
        fail('Native executable review identity is inconsistent.')
    _arguments(packet['identity']['argv'])
    recorded = packet['identity']
    if (recorded['coding_uid'] < 501
            or any(type(recorded[key]) is not int or recorded[key] < 0 for key in ('device', 'inode'))
            or any(not isinstance(recorded[key], str) or not recorded[key] or '\x00' in recorded[key]
                   for key in ('project', 'workspace', 'url', 'software'))):
        fail('Invalid recorded context identity.')
    from .client import _validate_values
    _validate_values(recorded['workspace'], recorded['url'], 'packet-validation')
    # Operator hashes exactly the escaped UTF-8 bytes it displays, including
    # prospective managed sources. No body survives into the public registry.
    inactive_root = _inactive_memory_root(packet['identity'])
    _validate_namespaces(packet['identity']['project'], Path(inactive_root).parent)
    for tree in (packet['current'],packet['prospective']):
        if not isinstance(tree,dict):fail('Invalid context inventory.')
        _require_auto_memory_disabled(tree, Path(inactive_root).parent / 'settings.json')
        inactive = tree.get(inactive_root)
        if (not isinstance(inactive, dict) or set(inactive) != {'inactive', 'present'}
                or type(inactive['inactive']) is not str or inactive['inactive'] != INACTIVE_AUTO_MEMORY
                or type(inactive['present']) is not bool):
            fail('Missing or malformed fixed inactive auto-memory root.')
        for path,entry in tree.items():
            if not isinstance(path,str) or not Path(path).is_absolute():fail('Invalid inventory path.')
            if entry is None or entry=={'directory':True} or entry == INERT_STATE:continue
            if path == inactive_root:
                continue
            if isinstance(entry,dict) and set(entry)=={'excluded','present'} and entry['excluded']=='credentials' and type(entry['present']) is bool:continue
            if (not isinstance(entry,dict) or set(entry)!={'text','sha256'} or not isinstance(entry['text'],str)
                    or digest(entry['text'].encode())!=entry['sha256']):fail('Review byte digest mismatch.')
    return hashes(packet)


def registry(fd, uid):
    try:
        value = parse(read_at(fd, 'registry.json', uid))
    except FileNotFoundError:
        fail('Context registry is missing; ask the operator to bootstrap the context authority.')
    except PermissionError:
        fail('Context registry is not readable; ask the operator to repair its published mode.')
    if (set(value) != {'version', 'generation', 'approval'} or value['version'] != 1
            or type(value['generation']) is not int or value['generation'] < 1
            or value['approval'] is not None and not isinstance(value['approval'], dict)):
        fail('Context registry is malformed or has a stale generation.')
    approval=value['approval']
    if approval is not None and (set(approval)!={'generation','packet'} or approval['generation']!=value['generation'] or not isinstance(approval['packet'],dict)):
        fail('Stale or malformed current approval generation.')
    return value


def _lock(fd, name, uid, private=False):
    _, opened, info = security.public_file_at(fd, name, uid, limit=128)
    if private:
        try:
            security._check_acl(opened,private=True)
            if stat.S_IMODE(info.st_mode)!=0o600:fail('Operator synchronisation lock must be private0600.')
        except BaseException:
            os.close(opened);raise
    return opened


def _publish(fd, value):
    name = '.registry-' + secrets.token_hex(16)
    opened = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=fd)
    try:
        with os.fdopen(opened, 'wb') as handle:
            os.fchmod(handle.fileno(), 0o644)
            handle.write(canonical(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, 'registry.json', src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    finally:
        try:
            os.unlink(name, dir_fd=fd)
        except FileNotFoundError:
            pass


def operator(packet=None, revoke=False):
    """Packet-free revoke uses only current protected registry and delegation."""
    from .client import ClientError
    approved=None if revoke else validate_packet(packet)
    with authority(None if revoke else packet['identity']['coding_uid']) as (fd,uid,software_digest):
        if os.getuid()!=uid:fail('Only the delegated operator may publish approval.')
        update=_lock(fd,'operator.lock',uid,private=True)
        try:
            try:fcntl.flock(update,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:fail('Another private operator update is active.')
            old=registry(fd,uid)
            if not revoke and packet['identity']['software']!=software_digest:fail('Protected software changed.')
            # shortcut: this first version supports ONE active project. Require
            # explicit revoke before changing project, never silently displace it.
            if not revoke and old['approval'] is not None:
                prior=old['approval']['packet']['identity']
                if any(prior[key]!=packet['identity'][key] for key in ('coding_uid','project','device','inode')):
                    fail('Explicitly revoke the active project before approving another.')
            displayed=old if revoke else packet
            confirmation=digest(canonical(displayed))
            with open('/dev/tty','r+',encoding='utf-8') as tty:
                tty.write(canonical(displayed).decode()+'\nType the complete review digest: '+confirmation+'\n')
                tty.flush()
                if tty.readline().strip()!=confirmation:fail('Context digest confirmation did not match.')
            generation=old['generation']+1
            value={'version':1,'generation':generation,
                   'approval':None if revoke else {'generation':generation,'packet':approved}}
            # Certainty is established BEFORE publication and must span it.
            # Failure to acquire stays uncertain even if a coding-held shared
            # lock is released during/after publication. Revoke still publishes.
            launch = None
            synchronised = False
            try:
                try:
                    launch = _lock(fd, 'launch.lock', uid)
                    until = time.monotonic() + 0.2
                    while True:
                        try:
                            fcntl.flock(launch, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            synchronised = True
                            break
                        except BlockingIOError:
                            remaining = until - time.monotonic()
                            if remaining <= 0:
                                break
                            time.sleep(min(0.01, remaining))
                except (OSError, ClientError, security.SecurityError):
                    if not revoke:
                        raise
                    # A broken synchronisation object must not preserve an old
                    # approval that could revive when that object is repaired.
                    synchronised = False
                # Publication/flush/fsync failures are deliberately NOT caught.
                _publish(fd, value)
            finally:
                if launch is not None:
                    os.close(launch)
        finally:
            os.close(update)
        return {'generation':generation,'revoked':revoke,'in_flight_launch_uncertain':not synchronised}


def export(project, workspace, url, instance, argv):
    with authority(os.getuid()) as (_, _, software_digest):
        return observe(project, workspace, url, instance, argv, software_digest)


@contextmanager
def decision(project, workspace, url, instance, argv):
    with authority(os.getuid()) as (fd, uid, software_digest):
        lock = _lock(fd, 'launch.lock', uid)
        try:
            try:
                fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                fail('Context launch authorisation is busy.')
            packet = observe(project, workspace, url, instance, argv, software_digest)
            seen = hashes(packet)
            current = registry(fd, uid)
            approved = None if current['approval'] is None else current['approval']['packet']
            if (approved is None or set(approved) != set(seen)
                    or approved['identity'] != seen['identity']
                    or approved['contract'] != seen['contract'] or approved['version'] != 1
                    or approved['excluded'] != list(EXCLUDED)
                    or seen['current'] not in (approved['current'], approved['prospective'])
                    or seen['prospective'] != approved['prospective']):
                fail('Context approval is missing, revoked, stripped or changed.')
            # The second current lookup catches a generation change during comparison;
            # observation precedes both reads and does not freeze later consumption.
            if registry(fd, uid) != current:
                fail('Context authority generation changed during authorisation.')
            yield packet
        finally:
            os.close(lock)
