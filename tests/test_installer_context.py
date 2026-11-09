"""Offline real-contract fixtures; native identity, roots and two-UID custody MOCKED.

The child is controlled Python, never an actual Claude client. No real config,
auth, Keychain, OS setup or service is read/changed. This is observed-local proof.
"""
from contextlib import contextmanager
import copy
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from memory_kit import client, context_authority as c, security

REAL_NATIVE = c._native
REAL_AUTHORITY = c.authority
REAL_SCOPE_ROOTS = c._scope_roots


class Store:
    def __init__(self):self.values={};self.effects=[]
    def check_ready(self):self.effects.append('ready')
    def get(self,instance,role):self.effects.append('get');return self.values.get(instance)
    def put(self,instance,role,value):self.effects.append('put');self.values[instance]=value


class LocalContextTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base=Path(self.temporary.name).resolve()
        self.project=self.base/'project';self.project.mkdir()
        self.home=self.base/'home';self.home.mkdir()
        self.config=self.home/'.claude';self.config.mkdir()
        self.managed=self.base/'managed';self.managed.mkdir()
        self.registry_root=self.base/'authority';self.registry_root.mkdir()
        self.uid=os.getuid();self.operator_uid=self.uid+1
        self.settings=self.config/'settings.json'
        self.settings.write_text(json.dumps({'autoMemoryEnabled':False,'model':'fixture-review',
                                             'permissions':{'defaultMode':'bypassPermissions'}}))
        self.capture=self.config/'commands/logthis.md';self.capture.parent.mkdir()
        self.capture.write_text('Fictional existing personal logthis: default and personal retain the previous route.\n')
        self.ancestor=self.base/'ancestor';self.ancestor.mkdir()
        self.instruction=self.ancestor/'CLAUDE.md';self.instruction.write_text('Fictional governing instructions.\n')
        self.binary=self.base/'fixture-versions/versions/2.1.318'
        self.binary.parent.mkdir(parents=True)
        self.binary.write_text('#!'+sys.executable+'''\nimport os,sys,json,pathlib
assert sys.argv[1:]==['--model','fixture-worker','--dangerously-skip-permissions']
assert os.environ['ANTHROPIC_AUTH_TOKEN']=='fictional-native-auth'
assert os.environ['AGENT_MEMORY_TOKEN'] in ('fixture-token','fixture-rotated')
p=pathlib.Path.cwd()
s=json.loads((pathlib.Path(os.environ['CLAUDE_CONFIG_DIR'])/'settings.json').read_text())
assert s['model']=='fixture-review' and s['autoMemoryEnabled'] is False
text=(p/'CLAUDE.md').read_text()
contract=json.loads(next(line.split(': ',1)[1] for line in text.splitlines() if line.startswith('Capture dispatch contract: ')))
assert contract['default']==contract['personal']=='prior route'
assert contract['explicit_business']=={'workspace':'business-fixture','tool':'memory_submit','state':'pending','approve':False,'publish':False}
assert (pathlib.Path(os.environ['CLAUDE_CONFIG_DIR'])/'commands/logthis.md').read_text().startswith('Fictional existing personal')
sys.exit(13)
''')
        self.binary.chmod(0o700)  # New isolated fixture executable only.
        self.argv=[str(self.binary),'--model','fixture-worker','--dangerously-skip-permissions']
        self.native_version='2.1.318'
        self.env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'HOME':str(self.home),
                  'CLAUDE_CONFIG_DIR':str(self.config),'ANTHROPIC_AUTH_TOKEN':'fictional-native-auth'}
        self.enterContext(patch.dict(os.environ,self.env,clear=True))
        self.enterContext(patch.object(client,'_home',return_value=self.home))
        self.enterContext(patch.object(c,'_roots',return_value=(self.home,self.config,self.managed,(self.base/'managed-preferences.plist',))))
        self.enterContext(patch.object(c,'_scope_roots',return_value=(self.project,self.ancestor)))
        def native(argv):
            if not isinstance(argv,list) or not argv:raise client.ClientError('missing argv')
            return {'path':str(self.binary.with_name(self.native_version)),'version':self.native_version,'sha256':c.digest(self.binary.read_bytes())}
        self.enterContext(patch.object(c,'_native',side_effect=native))
        @contextmanager
        def authority(coding_uid=None):
            fd=os.open(self.registry_root,os.O_RDONLY|os.O_DIRECTORY)
            try:yield fd,self.operator_uid,'fixture-software-digest'
            finally:os.close(fd)
        self.enterContext(patch.object(c,'authority',authority))
        self.enterContext(patch.object(client,'standard_coding_identity',return_value={'uid':self.uid}))
        self.enterContext(patch.object(security,'_check_volume'))
        self.enterContext(patch.object(security,'_check_acl'))
        real_file=security.public_file_at
        def public(fd,name,uid,limit=4*1024*1024):return real_file(fd,name,self.uid,limit)
        self.enterContext(patch.object(security,'public_file_at',side_effect=public))
        (self.registry_root/'registry.json').write_bytes(c.canonical({'version':1,'generation':1,'approval':None}))
        for name in ('operator.lock','launch.lock'):(self.registry_root/name).write_bytes(b'')
        (self.registry_root/'operator.lock').chmod(0o600)
        self.store=Store();self.args=(self.project,'business-fixture','http://127.0.0.1:4237/mcp')

    def packet(self):return c.export(*self.args,'fixture',self.argv)
    def approve(self,revoke=False):
        packet=None if revoke else self.packet()
        displayed=json.loads((self.registry_root/'registry.json').read_text()) if revoke else packet
        expected=c.digest(c.canonical(displayed))
        class TTY(io.StringIO):
            def readline(self,*args):return expected+'\n'
            def close(self):pass
        tty=TTY()
        with patch('builtins.open',return_value=tty),patch.object(c.os,'getuid',return_value=self.operator_uid):
            result=c.operator(packet,revoke=revoke)
        self.assertIn(c.canonical(displayed).decode(),tty.getvalue())
        return result
    def connect(self,instance='fixture',token=b'fixture-token'):
        return client.connect(*self.args,token,self.store,instance,native_argv=self.argv)
    def preflight(self,instance='fixture',rekey=False):
        return client.check_connection(*self.args,self.store,instance,self.uid,rekey=rekey,native_argv=self.argv)
    def launch(self):return client.run(self.project/client.PROFILE_NAME,self.argv,self.store)
    def tree(self):return {str(p.relative_to(self.project)):p.read_bytes() for p in self.project.rglob('*') if p.is_file()}
    def denied(self,call):
        before=self.tree();self.store.effects.clear()
        with patch.object(subprocess,'Popen') as child:
            with self.assertRaises((client.ClientError,security.SecurityError)):call()
            child.assert_not_called()
        self.assertEqual(self.store.effects,[]);self.assertEqual(self.tree(),before)

    def test_operator_packet_and_publication_never_open_coder_paths(self):
        packet = self.packet()
        expected = c.digest(c.canonical(packet))
        class TTY(io.StringIO):
            def readline(self, *args): return expected + '\n'
            def close(self): pass
        tty = TTY()
        real_directory, real_open = client._directory, os.open
        real_stat, real_lstat, real_io_open = os.stat, os.lstat, io.open
        def coder_path(path):
            path = Path(path)
            return any(path == root or root in path.parents for root in
                       (self.project, self.home, self.ancestor, self.binary.parent))
        @contextmanager
        def inaccessible(path):
            if coder_path(path): raise PermissionError('simulated other UID')
            with real_directory(path) as fd: yield fd
        def opened(path, *args, **kwargs):
            if isinstance(path, (str, Path)) and Path(path).is_absolute() and coder_path(path):
                raise PermissionError('simulated other UID')
            return real_open(path, *args, **kwargs)
        def metadata_probe(original):
            def probe(path, *args, **kwargs):
                if isinstance(path, (str, Path)) and Path(path).is_absolute() and coder_path(path):
                    raise PermissionError('simulated other UID')
                return original(path, *args, **kwargs)
            return probe
        def tty_open(path, *args, **kwargs):
            self.assertEqual(path, '/dev/tty')
            return tty
        with patch.object(client, '_directory', inaccessible), \
             patch.object(os, 'open', side_effect=opened), \
             patch.object(os, 'stat', side_effect=metadata_probe(real_stat)), \
             patch.object(os, 'lstat', side_effect=metadata_probe(real_lstat)), \
             patch.object(io, 'open', side_effect=metadata_probe(real_io_open)), \
             patch.object(c.os, 'getuid', return_value=self.operator_uid), \
             patch('builtins.open', side_effect=tty_open):
            self.assertEqual(c.validate_packet(packet), c.hashes(packet))
            self.assertEqual(c.operator(packet)['generation'], 2)
        self.assertTrue(self.preflight()['ready'])  # Coder re-observes independently.
        self.instruction.write_text('Changed after operator approval.')
        self.denied(self.preflight)

    def test_packet_identity_types_refuse_cleanly(self):
        packet = self.packet()
        for key in ('project', 'device', 'inode', 'workspace', 'url', 'software', 'coding_uid'):
            for value in (None, [], {}, True):
                forged = copy.deepcopy(packet); forged['identity'][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(client.ClientError):
                    c.validate_packet(forged)

    def test_inert_claude_state_is_accepted_without_values_in_packet_or_registry(self):
        marker = 'fictional-private-state-marker'
        state = {'numStartups': 4, 'userID': marker, 'oauthAccount': {'fixture': marker},
                 'projects': {str(self.project): {'lastCost': 1, 'lastSessionId': marker}}}
        paths = (self.home / '.claude.json', self.config / '.claude.json')
        for path in paths: path.write_text(json.dumps(state))
        packet = self.packet()
        self.assertNotIn(marker, c.canonical(packet).decode())
        for path in paths:
            self.assertEqual(packet['current'][str(path)]['excluded'], 'inert-claude-state')
        self.approve()
        for path in paths: path.write_text(json.dumps({**state, 'numStartups': 5}))
        self.assertTrue(self.preflight()['ready'])
        self.assertNotIn(marker, (self.registry_root / 'registry.json').read_text())
        alternate = self.home / 'alternate-config'; alternate.mkdir()
        (alternate / 'settings.json').write_bytes(self.settings.read_bytes())
        alternate.with_suffix('.json').write_text(json.dumps(state))
        with patch.object(c, '_roots', return_value=(self.home, alternate, self.managed, ())):
            self.assertEqual(self.packet()['current'][str(alternate.with_suffix('.json'))]['excluded'],
                             'inert-claude-state')

    def test_claude_state_refuses_context_and_unknown_keys_at_both_scopes(self):
        path = self.home / '.claude.json'
        for key in ('mcpServers', 'mcpContextUris', 'enabledMcpjsonServers', 'disabledMcpjsonServers',
                    'enabledMcpServers', 'disabledMcpServers', 'enableAllProjectMcpServers',
                    'hasClaudeMdExternalIncludesApproved', 'hasTrustDialogAccepted', 'allowedTools',
                    'hooks', 'env', 'permissions', 'autoMemoryDirectory', 'futureUnknownKey'):
            for state in ({key: {}}, {'projects': {str(self.project): {key: []}}}):
                path.write_text(json.dumps(state))
                with self.subTest(key=key, project='projects' in state), self.assertRaises(client.ClientError):
                    self.packet()
        for state in ({'projects': []}, {'projects': {'fixture': []}}):
            path.write_text(json.dumps(state))
            with self.assertRaises(client.ClientError): self.packet()

    def test_observe_has_three_full_plan_checks_including_final_postread(self):
        real_check, real_read = c._check_plan, c._read
        events = []
        def check(metadata): events.append('check'); return real_check(metadata)
        def read(path): events.append('read'); return real_read(path)
        with patch.object(c, '_check_plan', side_effect=check), patch.object(c, '_read', side_effect=read):
            self.packet()
        self.assertEqual(events.count('check'), 3)
        self.assertEqual(events[-1], 'check')

    def test_registry_mode_is_independent_of_operator_umask(self):
        fd = os.open(self.registry_root, os.O_RDONLY | os.O_DIRECTORY)
        previous = os.umask(0o077)
        try: c._publish(fd, {'version': 1, 'generation': 2, 'approval': None})
        finally: os.umask(previous); os.close(fd)
        self.assertEqual(stat.S_IMODE((self.registry_root / 'registry.json').stat().st_mode), 0o644)

    def test_unreadable_registry_has_clear_refusal(self):
        with patch.object(c, 'read_at', side_effect=PermissionError('fixture')):
            with self.assertRaisesRegex(client.ClientError, 'registry.*readable'):
                c.registry(-1, self.uid)

    def test_native_executable_refuses_group_writable_parent(self):
        self.binary.write_bytes(b'\xcf\xfa\xed\xfe' +
            b'README_URL:"https://code.claude.com/docs/en/overview",VERSION:"2.1.318"')
        self.binary.parent.chmod(0o775)  # Isolated fixture only.
        with self.assertRaisesRegex(client.ClientError, 'executable.*custody'):
            REAL_NATIVE(self.argv)

    def test_integrated_native_contract_approval_lifecycle(self):
        packet=self.packet()
        self.assertEqual(packet['contract'],'claude-code/2.1.318')
        self.assertEqual(packet['excluded'],list(c.EXCLUDED))
        self.assertNotIn('fictional-native-auth',c.canonical(packet).decode())
        original={p:p.read_bytes() for p in (self.settings,self.capture,self.instruction)}
        self.denied(self.connect)
        self.assertEqual(self.approve()['generation'],2)
        before=self.tree();self.assertTrue(self.preflight()['ready']);self.assertEqual(before,self.tree())
        first=self.connect();self.assertEqual(first,self.connect())
        self.assertEqual(self.launch(),13)
        self.assertTrue(self.preflight('rotated',True)['ready'])
        client.reconnect(*self.args,b'fixture-rotated',self.store,'rotated',native_argv=self.argv)
        self.assertEqual(self.launch(),13)
        self.assertEqual(original,{p:p.read_bytes() for p in original})
        self.capture.write_text(self.capture.read_text()+'Changed local context.\n')
        self.denied(self.launch)
        self.assertTrue(self.approve(revoke=True)['revoked'])
        self.denied(self.launch)
        self.assertNotIn('fictional-native-auth',(self.registry_root/'registry.json').read_text())
        print('ACCEPTED_SYNTHETIC_LOCAL_WORKFLOW: export -> canonicalTTYapprove -> readonlypreflight -> connect -> boundconnect -> actualPythonchild13/models/auth/dispatch -> rotate/reconnect -> child13 -> changedlocalDENY beforeeffects -> packetFreeREVOKE -> DENY; native identity/roots/UID/custody MOCKED',flush=True)

    def test_21319_packet_selects_observed_contract(self):
        self.native_version='2.1.319'
        packet=self.packet()
        self.assertEqual(packet['contract'],'claude-code/2.1.319')
        self.assertEqual(c.validate_packet(packet),c.hashes(packet))
        self.approve()
        self.assertTrue(self.preflight()['ready'])

    def test_packet_executable_self_consistency_refusals(self):
        packet=self.packet()
        executable=packet['identity']['executable']
        invalid=[None, [], {**executable,'extra':True}]
        invalid += [{key:value for key,value in executable.items() if key!=missing}
                    for missing in executable]
        invalid += [{**executable,'version':value} for value in ('2.1.320',None,[])]
        invalid += [{**executable,'path':value} for value in
                    (str(self.binary.with_name('2.1.319')),str(self.base/'2.1.318'),None,[])]
        invalid += [{**executable,'sha256':value} for value in
                    ('a'*63,'a'*65,'A'*64,'g'*64,'a'*63+'\n',None,[])]
        for value in invalid:
            forged=copy.deepcopy(packet)
            forged['identity']['executable']=value
            with self.subTest(executable=value),self.assertRaises(client.ClientError):
                c.validate_packet(forged)
        forged=copy.deepcopy(packet);forged['contract']='claude-code/2.1.319'
        with self.assertRaises(client.ClientError):c.validate_packet(forged)

    def test_operator_approval_needs_no_coder_executable_or_path(self):
        packets=[]
        for command in ('claude',str(self.binary)):
            self.argv[0]=command
            packets.append(copy.deepcopy(self.packet()))
        self.binary.unlink()  # Coder's executable is unavailable to this operator fixture.
        for packet in packets:
            with self.subTest(command=packet['identity']['argv'][0]), \
                    patch.dict(os.environ,{'PATH':str(self.base/'operator-only-path')}), \
                    patch.object(c,'export',return_value=packet), \
                    patch.object(c,'_native',side_effect=PermissionError('coder executable inaccessible')) as native:
                self.approve()
                native.assert_not_called()
                approved=json.loads((self.registry_root/'registry.json').read_text())['approval']['packet']
                self.assertEqual(approved,c.hashes(packet))

    def test_launch_refuses_approved_contract_drift(self):
        self.approve()
        registry=json.loads((self.registry_root/'registry.json').read_text())
        registry['approval']['packet']['contract']='claude-code/2.1.319'
        (self.registry_root/'registry.json').write_bytes(c.canonical(registry))
        self.denied(self.preflight)

    def test_packet_argument_schema_remains_checked_without_native_lookup(self):
        packet=self.packet()
        for argv in (None,[], 'claude',[None],[''],['claude','\x00'],['claude','--model']):
            forged=copy.deepcopy(packet);forged['identity']['argv']=argv
            with self.subTest(argv=argv),self.assertRaises(client.ClientError):
                c.validate_packet(forged)

    def test_launch_refuses_resolved_release_and_sha_changes(self):
        versions=self.base/'versions';versions.mkdir()
        for version in ('2.1.318','2.1.319'):
            (versions/version).write_bytes(b'\xcf\xfa\xed\xfe'+
                f'README_URL:"https://code.claude.com/docs/en/overview",VERSION:"{version}"'.encode())
            (versions/version).chmod(0o700)  # New isolated fixture only.
        self.binary.unlink();self.binary.symlink_to(versions/'2.1.318')
        with patch.object(c,'_native',side_effect=REAL_NATIVE):
            packet=self.packet()
            self.approve()
            self.assertTrue(self.preflight()['ready'])
            self.connect()
            alternate=self.base/'alternate/versions';alternate.mkdir(parents=True)
            other=alternate/'2.1.318';other.write_bytes((versions/'2.1.318').read_bytes())
            other.chmod(0o700)  # New isolated fixture only; same version and bytes, different path.
            self.binary.unlink();self.binary.symlink_to(other)
            self.assertEqual(c.validate_packet(packet),c.hashes(packet))
            self.denied(self.launch)
            self.binary.unlink();self.binary.symlink_to(versions/'2.1.319')
            self.assertEqual(c.validate_packet(packet),c.hashes(packet))
            self.denied(self.launch)
            self.denied(self.connect)
            self.binary.unlink();self.binary.symlink_to(versions/'2.1.318')
            with (versions/'2.1.318').open('ab') as binary:binary.write(b'changed bytes')
            self.assertEqual(c.validate_packet(packet),c.hashes(packet))
            self.denied(self.launch)
            self.denied(self.connect)

    def test_run_argv_names_use_explicit_contracts_before_authorisation(self):
        self.approve();self.connect()
        for name in ('claude','2.1.318','2.1.319','2.1.317','2.1.320'):
            with self.subTest(name=name),patch.object(client,'_check_logthis') as early, \
                    patch.object(c,'decision',side_effect=client.ClientError('fixture stop')):
                with self.assertRaisesRegex(client.ClientError,'fixture stop'):
                    client.run(self.project/client.PROFILE_NAME,[str(self.base/name)],self.store)
                early.assert_not_called()  # Native identity is checked only by decision().

    @contextmanager
    def foreign_memory_guard(self, projects):
        real_open, real_close = os.open, os.close
        real_scandir, real_listdir = os.scandir, os.listdir
        real_iterdir, real_read = Path.iterdir, c._read
        descriptors = {}
        def checked(path, dir_fd=None):
            if isinstance(path, int):
                self.assertIn(path, descriptors, 'Untracked directory descriptor')
                absolute = descriptors[path]
            else:
                absolute = Path(os.fsdecode(path))
                if not absolute.is_absolute():
                    if dir_fd is not None:
                        self.assertIn(dir_fd, descriptors, 'Untracked relative open descriptor')
                        absolute = descriptors[dir_fd] / absolute
                    else:
                        absolute = Path.cwd() / absolute
            self.assertFalse(absolute == projects or projects in absolute.parents,
                             'Foreign memory enumeration/read/open reached')
            return absolute
        def opened(path, flags, mode=0o777, *, dir_fd=None):
            absolute = checked(path, dir_fd)
            fd = real_open(path, flags, mode, dir_fd=dir_fd)
            descriptors[fd] = absolute
            return fd
        def closed(fd):
            descriptors.pop(fd, None)
            return real_close(fd)
        with patch.object(os, 'open', side_effect=opened), \
                patch.object(os, 'close', side_effect=closed), \
                patch.object(os, 'scandir', side_effect=lambda path: real_scandir(checked(path))), \
                patch.object(os, 'listdir', side_effect=lambda path: real_listdir(checked(path))), \
                patch.object(Path, 'iterdir', lambda path: real_iterdir(checked(path))), \
                patch.object(c, '_read', side_effect=lambda path: real_read(checked(path))):
            yield

    def test_regular_private_directory_swap_is_denied_before_body_read(self):
        active = self.project / 'active'
        active.mkdir()
        (active / 'CLAUDE.md').write_text('original instruction')
        private = self.config / 'projects'
        private.mkdir()
        (private / 'CLAUDE.md').write_text('foreign moved instruction')
        original = c._classified
        swapped = []
        def replace_before_read(path, kind='markdown'):
            if Path(path) == active / 'CLAUDE.md' and not swapped:
                active.rename(self.project / 'retired-active')
                private.rename(active)
                swapped.append(True)
            return original(path, kind)
        real_read = os.read
        def no_foreign_read(fd, count):
            info = os.fstat(fd)
            self.assertNotEqual(info.st_ino, (active / 'CLAUDE.md').stat().st_ino
                                if swapped else -1, 'Foreign moved body reached read')
            return real_read(fd, count)
        with patch.object(c, '_classified', side_effect=replace_before_read), patch.object(os, 'read', side_effect=no_foreign_read):
            with self.assertRaises(client.ClientError): self.packet()
        self.assertEqual(swapped, [True])

    def test_descriptor_listing_denies_regular_directory_swap(self):
        active = self.project / 'active-listing'
        active.mkdir()
        private = self.config / 'projects'
        private.mkdir()
        real_listing = c._listed_directory
        swapped = []
        @contextmanager
        def replace_listing(path, metadata):
            if Path(path) == active and not swapped:
                active.rename(self.project / 'retired-listing')
                private.rename(active)
                swapped.append(True)
            with real_listing(path, metadata) as result:
                yield result
        with patch.object(c, '_listed_directory', replace_listing):
            with self.assertRaises(client.ClientError): self.packet()
        self.assertEqual(swapped, [True])

    def test_binding_snapshot_denies_planned_directory_move_before_read(self):
        active = self.project / '.codex'
        active.mkdir()
        (active / 'config.toml').write_text('model="fixture"')
        private = self.config / 'projects'
        private.mkdir()
        (private / 'config.toml').write_text('foreign moved body')
        _, _, metadata, _ = c._plan_sources(self.project)
        active.rename(self.base / 'retired-codex')
        private.rename(active)
        with client._planned_io(metadata), patch.object(client.os, 'fdopen', side_effect=AssertionError('foreign binding read')):
            with self.assertRaises(client.ClientError): client._snapshot(active / 'config.toml')
        self.assertIsNone(client._PLANNED_IO.get())
        with client._planned_io(metadata):
            with client._planned_io(metadata): pass
            self.assertIs(client._PLANNED_IO.get(), metadata)
        self.assertIsNone(client._PLANNED_IO.get())

    def test_public_run_refused_plan_precedes_all_early_readers(self):
        with patch.object(c, '_plan_sources', side_effect=client.ClientError('plan refused')), \
                patch.object(client, '_load_profile') as profile, \
                patch.object(client, '_check_logthis') as fallback, \
                patch.object(self.store, 'get') as credential, \
                patch.object(subprocess, 'Popen') as child:
            with self.assertRaisesRegex(client.ClientError, 'plan refused'):
                client.run(self.project / client.PROFILE_NAME, self.argv, self.store)
        for operation in (profile, fallback, credential, child): operation.assert_not_called()

    def test_real_home_ancestor_uses_selected_global_config_slots(self):
        project = self.home / 'Projects' / 'app'
        project.mkdir(parents=True)
        (self.config / 'projects').mkdir()
        (self.config / 'history.jsonl').write_text('fictional unrelated history')
        self.assertEqual(client._project(project), project)
        with patch.object(c, '_scope_roots', REAL_SCOPE_ROOTS), self.foreign_memory_guard(self.config / 'projects'):
            packet = c.export(project, 'business-fixture', self.args[2], 'fixture', self.argv)
        self.assertEqual(packet['current'][str(self.config / 'settings.json')]['sha256'], c.digest(self.settings.read_bytes()))
        self.assertNotIn('fictional unrelated history', c.canonical(packet).decode())

    def test_metadata_check_count_is_linear_in_planned_paths(self):
        for index in range(24): (self.project / ('dir'+str(index))).mkdir()
        real_plan, real_metadata = c._plan_sources, c._path_metadata
        sizes = []
        def sized_plan(project):
            plan = real_plan(project)
            sizes.append(len(plan[2]['paths']))
            return plan
        with patch.object(c, '_plan_sources', side_effect=sized_plan), \
                patch.object(c, '_path_metadata', wraps=real_metadata) as checks:
            self.packet()
        self.assertLessEqual(checks.call_count, 12 * sizes[0])

    def test_plan_is_metadata_only_and_covers_binding_slots(self):
        with patch.object(c, '_classified', side_effect=AssertionError('classification during discovery')), \
                patch.object(c, '_read', side_effect=AssertionError('body during discovery')), \
                patch.object(client, '_snapshot', side_effect=AssertionError('binding during discovery')):
            inventory, slots, metadata, config = c._plan_sources(self.project)
        self.assertEqual(config, self.config)
        for name in client._FILES:
            self.assertIn(str(self.project / name), slots)
        self.assertIn(str(self.project / client.PROFILE_NAME), metadata['paths'])

    def test_plan_boundary_rejects_added_absent_slot_and_file_drift_before_reads(self):
        real_plan = c._plan_sources
        for mode in ('added', 'changed'):
            with self.subTest(mode=mode):
                def changed_plan(project):
                    plan = real_plan(project)
                    if mode == 'added': (self.project / 'CLAUDE.md').write_text('new instruction')
                    else: self.instruction.write_text('changed governing instruction')
                    return plan
                with patch.object(c, '_plan_sources', side_effect=changed_plan), \
                        patch.object(c, '_classified', side_effect=AssertionError('body after plan drift')):
                    with self.assertRaises(client.ClientError): self.packet()
                if mode == 'added': (self.project / 'CLAUDE.md').unlink()

    def test_review_refuses_managed_preferences_added_after_planning(self):
        preferences = self.base / 'managed-preferences.plist'
        real_plan = c._plan_sources
        def add_preferences(project):
            plan = real_plan(project)
            preferences.write_text('Fictional unsupported managed preferences.')
            return plan
        with patch.object(c, '_plan_sources', side_effect=add_preferences):
            with self.assertRaises(client.ClientError,
                                   msg='Export returned stale managed-preference absence'):
                self.packet()
        self.assertTrue(preferences.is_file())
        with self.assertRaises(client.ClientError): self.packet()
        self.assertEqual(self.store.effects, [])

    def test_review_refuses_project_replacement_before_final_plan_check(self):
        source = self.project / 'CLAUDE.md'
        source.write_text('Fictional ORIGINAL reviewed instructions.\n')
        original_inode = self.project.stat().st_ino
        real_check = c._check_plan
        checks = []
        def replace_project(metadata):
            real_check(metadata)
            checks.append(True)
            if len(checks) == 2:
                self.project.rename(self.base / 'previous-project')
                self.project.mkdir()
                source.write_text('Fictional REPLACEMENT unreviewed instructions.\n')
        with patch.object(c, '_check_plan', side_effect=replace_project):
            with self.assertRaises(client.ClientError,
                                   msg='Export paired replacement identity with ORIGINAL inventory'):
                self.packet()
        self.assertGreaterEqual(len(checks), 2)
        self.assertNotEqual(self.project.stat().st_ino, original_inode)
        self.assertIn('ORIGINAL', (self.base / 'previous-project' / 'CLAUDE.md').read_text())
        self.assertIn('REPLACEMENT', source.read_text())
        self.assertEqual(self.store.effects, [])

    def test_review_credentials_presence_uses_planned_metadata(self):
        """Fictional credentials exist at planning and every plan check; only
        the unplanned lexists probe reports controlled absence. Native identity,
        roots and UID/custody are mocked; no credentials body is read.
        """
        credential = self.config / '.credentials.json'
        credential.write_text('Fictional excluded credentials fixture.')
        real_exists, real_check, real_read = os.path.lexists, c._check_plan, c._read
        checks = []
        def absent_probe(path):
            return False if Path(path) == credential else real_exists(path)
        def check_with_credential(metadata):
            self.assertTrue(credential.is_file())
            checks.append(True)
            return real_check(metadata)
        def read_without_credentials(path, *args, **kwargs):
            self.assertNotEqual(Path(path), credential, 'Credentials body was read')
            return real_read(path, *args, **kwargs)
        self.assertTrue(credential.is_file())
        with patch.object(os.path, 'lexists', side_effect=absent_probe), \
                patch.object(c, '_check_plan', side_effect=check_with_credential), \
                patch.object(c, '_read', side_effect=read_without_credentials):
            packet = self.packet()
        self.assertTrue(checks)
        self.assertTrue(credential.is_file())
        self.assertTrue(packet['current'][str(credential)]['present'],
                        'Export reported credentials absent despite presence at every plan check')
        self.assertEqual(self.store.effects, [])

    def test_review_project_identity_stays_paired_after_final_plan_check(self):
        """Fictional project swaps immediately after the final real plan check;
        native identity, roots and UID/custody are mocked. The packet must keep
        ORIGINAL planned identity and instructions together after that swap.
        """
        source = self.project / 'CLAUDE.md'
        original_text = 'Fictional ORIGINAL reviewed instructions.\n'
        source.write_text(original_text)
        original_inode = self.project.stat().st_ino
        real_check = c._check_plan
        with patch.object(c, '_check_plan', wraps=real_check) as baseline_checks:
            self.packet()
        final_call = baseline_checks.call_count
        self.assertGreater(final_call, 0)
        checks = []
        def replace_after_final_check(metadata):
            real_check(metadata)
            checks.append(True)
            if len(checks) == final_call:
                self.project.rename(self.base / 'previous-project')
                self.project.mkdir()
                source.write_text('Fictional REPLACEMENT unreviewed instructions.\n')
        with patch.object(c, '_check_plan', side_effect=replace_after_final_check):
            packet = self.packet()
        self.assertEqual(len(checks), final_call)
        self.assertNotEqual(self.project.stat().st_ino, original_inode)
        self.assertEqual(packet['identity']['inode'], original_inode,
                         'Export paired replacement identity with ORIGINAL inventory')
        self.assertEqual(packet['current'][str(source)]['text'], original_text)
        self.assertIn('REPLACEMENT', source.read_text())
        self.assertEqual(self.store.effects, [])

    def test_review_refuses_skill_directory_aba_after_remembered_presence(self):
        """Fictional fixture, controlled interleaving, parent mtime restored;
        native identity/UID/custody mocked; not a native or host exploit.
        """
        skills = self.project / '.claude' / 'skills'
        skills.mkdir(parents=True)
        hidden = skills / 'hidden.md'
        hidden.write_text('Fictional ABA omitted source.')
        parent = skills.parent
        original = parent.stat()
        parked = self.base / 'parked-skills'
        real_remember, real_tree = c._remember_metadata, c._tree
        events = []
        collector_active = False
        def move_after_remember(path, metadata):
            value = real_remember(path, metadata)
            if Path(path) == skills and collector_active and not events:
                skills.rename(parked)
                events.append('moved after remembered')
            return value
        def restore_after_collection(path, inventory, slots, metadata):
            nonlocal collector_active
            if Path(path) != skills:
                return real_tree(path, inventory, slots, metadata)
            collector_active = True
            try:
                return real_tree(path, inventory, slots, metadata)
            finally:
                collector_active = False
                if parked.exists():
                    parked.rename(skills)
                    os.utime(parent, ns=(original.st_atime_ns, original.st_mtime_ns))
                    events.append('restored before checks')
        with patch.object(c, '_remember_metadata', side_effect=move_after_remember), \
                patch.object(c, '_tree', side_effect=restore_after_collection):
            with self.assertRaises(client.ClientError,
                                   msg='Export returned absent skills receipt and omitted existing hidden.md'):
                client.check_connection(*self.args, self.store, 'fixture', self.uid,
                                        native_argv=self.argv, review_context=True)
        self.assertEqual(events, ['moved after remembered', 'restored before checks'])
        self.assertTrue(hidden.is_file())
        self.assertEqual(parent.stat().st_mtime_ns, original.st_mtime_ns)
        self.assertEqual(self.store.effects, [])

    def test_private_cache_alias_denied_before_discovery_or_body_reads(self):
        foreign = self.project / 'cached-foreign' / 'foreign-project' / 'memory'
        foreign.mkdir(parents=True)
        (foreign / 'CLAUDE.md').write_text('fictional cache alias poison')
        (self.config / 'projects').symlink_to(self.project / 'cached-foreign', target_is_directory=True)
        self.assertEqual(client._project(self.project), self.project)
        with self.foreign_memory_guard(self.project / 'cached-foreign'):
            with self.assertRaises(client.ClientError): self.packet()

    def test_all_static_roots_admitted_before_any_context_body(self):
        linked = self.ancestor / '.claude' / 'skills'
        linked.parent.mkdir()
        linked.symlink_to(self.config, target_is_directory=True)
        self.assertEqual(client._project(self.project), self.project)
        with patch.object(c, '_classified', side_effect=AssertionError('Body before all-root admission')), \
                patch.object(client, '_snapshot', side_effect=AssertionError('Binding body before admission')):
            with self.assertRaises(client.ClientError): self.packet()

    def test_valid_project_nested_native_config_denies_before_foreign_walk(self):
        config = self.project / 'cfg'
        foreign = config / 'projects' / 'foreign-overlap-project' / 'memory'
        foreign.mkdir(parents=True)
        (config / 'settings.json').write_text('{"autoMemoryEnabled":false}')
        for name in ('CLAUDE.md', 'AGENTS.md'):
            (foreign / name).write_text('fictional foreign instruction poison')
        with patch.dict(os.environ, {'CLAUDE_CONFIG_DIR': str(config)}), \
                patch.object(c, '_roots', return_value=(self.home, config, self.managed, ())):
            self.assertEqual(client._project(self.project), self.project)
            with self.foreign_memory_guard(config / 'projects'):
                with self.assertRaises(client.ClientError):
                    client.check_connection(*self.args, self.store, 'fixture', self.uid,
                                            native_argv=self.argv, review_context=True)
                self.store.effects.clear()
                with patch.object(client, '_replace') as write, patch.object(subprocess, 'Popen') as child:
                    with self.assertRaises(client.ClientError): self.connect()
                    write.assert_not_called()
                    child.assert_not_called()
                self.assertEqual(self.store.effects, [])
                self.assertFalse((self.project / '.codex').exists())
                self.assertFalse((self.project / client.PROFILE_NAME).exists())

    def test_native_config_aliases_refuse_before_body_reads_and_packet_intake(self):
        packet = self.packet()
        for alias in (self.base / 'config-alias', self.base / 'parent-alias' / '.claude'):
            if alias.name == 'config-alias':
                alias.symlink_to(self.config, target_is_directory=True)
            else:
                alias.parent.symlink_to(self.home, target_is_directory=True)
            with patch.dict(os.environ, {'CLAUDE_CONFIG_DIR': str(alias)}), \
                    patch.object(c, '_roots', return_value=(self.home, alias, self.managed, ())), \
                    patch.object(c, '_read', side_effect=AssertionError('Alias reached a context body read')), \
                    patch.object(os, 'scandir', side_effect=AssertionError('Alias reached a source walk')):
                with self.assertRaises(client.ClientError): self.packet()
                self.store.effects.clear()
                with patch.object(client, '_replace') as write, patch.object(subprocess, 'Popen') as child:
                    with self.assertRaises(client.ClientError): self.connect()
                    write.assert_not_called()
                    child.assert_not_called()
                self.assertEqual(self.store.effects, [])
                self.assertFalse((self.project / '.codex').exists())
                self.assertFalse((self.project / client.PROFILE_NAME).exists())
            forged = copy.deepcopy(packet)
            forged['identity']['environment']['CLAUDE_CONFIG_DIR'] = str(alias)
            with self.assertRaises(client.ClientError): c.validate_packet(forged)
        forged = copy.deepcopy(packet)
        forged['identity']['environment']['CLAUDE_CONFIG_DIR'] = str(self.project / 'cfg')
        with self.assertRaises(client.ClientError): c.validate_packet(forged)

    def test_revoke_does_not_swallow_publication_errors(self):
        self.approve()
        before = (self.registry_root / 'registry.json').read_bytes()
        with patch.object(c, '_publish', side_effect=OSError('fictional fsync failure')):
            with self.assertRaisesRegex(OSError, 'fictional fsync failure'):
                self.approve(revoke=True)
        self.assertEqual((self.registry_root / 'registry.json').read_bytes(), before)

    def test_revoke_broken_launch_lock_and_flock_error_still_publish(self):
        import errno
        self.approve()
        lock = self.registry_root / 'launch.lock'
        for failure in ('missing', 'unsafe', 'flock'):
            lock.write_bytes(b'')
            with self.subTest(failure=failure):
                before = json.loads((self.registry_root / 'registry.json').read_text())
                if failure == 'missing': lock.unlink()
                elif failure == 'unsafe': lock.write_bytes(b'x' * 129)
                real_flock = c.fcntl.flock
                def flock(fd, operation):
                    if failure == 'flock' and operation == (c.fcntl.LOCK_EX | c.fcntl.LOCK_NB):
                        if os.fstat(fd).st_ino == lock.stat().st_ino:
                            raise OSError(errno.ENOLCK, 'fictional lock failure')
                    return real_flock(fd, operation)
                with patch.object(c.fcntl, 'flock', side_effect=flock):
                    # Approval must still fail and preserve the current generation.
                    with self.assertRaises((client.ClientError, security.SecurityError, OSError)):
                        self.approve()
                    self.assertEqual(json.loads((self.registry_root / 'registry.json').read_text()), before)
                    result = self.approve(revoke=True)
                after = json.loads((self.registry_root / 'registry.json').read_text())
                self.assertIsNone(after['approval'])
                self.assertEqual(after['generation'], before['generation'] + 1)
                self.assertTrue(result['in_flight_launch_uncertain'])
                lock.write_bytes(b'')
                self.denied(self.connect)  # Repairing the lock cannot resurrect approval.
                self.approve()

    def test_inactive_memory_never_enumerates_foreign_projects_during_workflow(self):
        projects = self.config / 'projects'
        foreign = projects / 'foreign-only-project' / 'memory'
        foreign.mkdir(parents=True)
        marker = 'fictional-foreign-body-marker'
        (foreign / 'MEMORY.md').write_text(marker)
        real_publish = c._publish
        def checked_publish(fd, value):
            encoded = c.canonical(value).decode()
            for private in (marker, 'foreign-only-project', str(foreign)):
                self.assertNotIn(private, encoded)
            return real_publish(fd, value)
        with self.foreign_memory_guard(projects), patch.object(c, '_publish', side_effect=checked_publish):
            packet = self.packet()
            expected = {'inactive': 'auto-memory-disabled/v1', 'present': True}
            self.assertEqual(packet['current'][str(projects)], expected)
            self.assertEqual(packet['prospective'][str(projects)], expected)
            for private in (marker, 'foreign-only-project', str(foreign)):
                self.assertNotIn(private, c.canonical(packet).decode())
            self.test_integrated_native_contract_approval_lifecycle()

    def test_revoke_release_at_publication_keeps_uncertainty_sticky(self):
        self.approve()
        held = subprocess.Popen([sys.executable, '-c',
            'import fcntl,sys; f=open(sys.argv[1]); fcntl.flock(f,fcntl.LOCK_SH); '
            'print("held",flush=True); sys.stdin.read()',
            str(self.registry_root / 'launch.lock')],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        real_publish = c._publish
        released = []
        try:
            self.assertEqual(held.stdout.readline().strip(), 'held')
            def release_after_publish(fd, value):
                real_publish(fd, value)
                if value['approval'] is None:
                    held.communicate('', timeout=3)
                    released.append(True)
            with patch.object(c, '_publish', side_effect=release_after_publish):
                start = time.monotonic()
                result = self.approve(revoke=True)
            self.assertLess(time.monotonic() - start, 1)
            self.assertEqual(released, [True])
            self.assertTrue(result['revoked'])
            self.assertTrue(result['in_flight_launch_uncertain'],
                            'Publication occurred without owning the exclusive launch lock')
            self.denied(self.connect)
        finally:
            if held.poll() is None:
                held.communicate('', timeout=3)

    def test_inactive_memory_schema_and_disabled_policy_cannot_hide_active_inputs(self):
        projects = self.config / 'projects'
        packet = self.packet()
        self.assertEqual(packet['current'][str(projects)],
                         {'inactive': 'auto-memory-disabled/v1', 'present': False})
        for entry in ({'inactive': 'unknown/v1', 'present': False},
                      {'inactive': 'auto-memory-disabled/v1', 'present': 0},
                      {'inactive': True, 'present': False},
                      {'inactive': 'auto-memory-disabled/v1', 'present': False, 'extra': True},
                      None, {'directory': True}):
            with self.subTest(entry=entry):
                forged = copy.deepcopy(packet)
                forged['current'][str(projects)] = entry
                with self.assertRaises(client.ClientError):
                    c.validate_packet(forged)
        forged = copy.deepcopy(packet)
        forged['prospective'][str(self.project / 'hidden-active-input')] = {
            'inactive': 'auto-memory-disabled/v1', 'present': True}
        with self.assertRaises(client.ClientError):
            c.validate_packet(forged)
        # A valid inactive tag cannot authorise enabled or absent local policy.
        for value in (True, None):
            forged = copy.deepcopy(packet)
            settings = {'model': 'fixture-review'}
            if value is not None:
                settings['autoMemoryEnabled'] = value
            body = json.dumps(settings)
            forged['current'][str(self.settings)] = {'text': body, 'sha256': c.digest(body.encode())}
            with self.subTest(packet_policy=value), self.assertRaises(client.ClientError):
                c.validate_packet(forged)
        foreign = projects / 'foreign-policy-fixture' / 'memory'
        foreign.mkdir(parents=True)
        (foreign / 'MEMORY.md').write_text('fictional foreign private marker')
        with self.foreign_memory_guard(projects):
            for value in (True, None, 'false'):
                settings = {'model': 'fixture-review'}
                if value is not None:
                    settings['autoMemoryEnabled'] = value
                self.settings.write_text(json.dumps(settings))
                with self.subTest(observed_policy=value):
                    self.denied(self.connect)

    def test_inactive_memory_requires_current_user_policy_not_ancestor_false(self):
        self.settings.write_text(json.dumps({'model': 'fixture-review'}))
        unrelated_settings = self.ancestor / '.claude' / 'settings.json'
        unrelated_settings.parent.mkdir()
        unrelated_settings.write_text(json.dumps({'autoMemoryEnabled': False}))
        # An observed ancestor setting is not proof the selected user's current
        # native configuration disables auto-memory. Keep this subset narrower.
        with self.assertRaises(client.ClientError):
            self.packet()

    def test_uncontended_certainty_holds_exclusive_lock_across_publication(self):
        real_publish = c._publish
        checked = []
        def assert_exclusive_then_publish(fd, value):
            # An independent process must be unable to enter SH while the
            # operator claims certainty and atomically publishes its generation.
            script = ('import fcntl,sys; f=open(sys.argv[1]); '
                      '\ntry: fcntl.flock(f,fcntl.LOCK_SH|fcntl.LOCK_NB)'
                      '\nexcept BlockingIOError: sys.exit(0)'
                      '\nelse: sys.exit(9)')
            probe = subprocess.run([sys.executable, '-c', script,
                                    str(self.registry_root / 'launch.lock')], timeout=3)
            self.assertEqual(probe.returncode, 0, 'Exclusive launch lock absent during publication')
            checked.append(value['generation'])
            return real_publish(fd, value)
        with patch.object(c, '_publish', side_effect=assert_exclusive_then_publish):
            approval = self.approve()
            revoke = self.approve(revoke=True)
        self.assertEqual(checked, [2, 3])
        self.assertFalse(approval['in_flight_launch_uncertain'])
        self.assertFalse(revoke['in_flight_launch_uncertain'])
        self.assertTrue(revoke['revoked'])

    def test_unknown_flags_environment_imports_plugins_refuse(self):
        self.approve()
        saved=self.argv[:]
        for flag in ('--settings','--add-dir','--mcp-config','--append-system-prompt','--resume','--plugin-dir'):
            self.argv=saved+[flag,'fictional'];self.denied(self.connect)
        self.argv=saved
        with patch.dict(os.environ,{'CLAUDE_CODE_PLUGIN_DIRS':'/fictional/plugin'}):self.denied(self.connect)
        with patch.dict(os.environ,{'GIT_DIR':'/fictional/git'}):self.denied(self.connect)
        self.instruction.write_text('@outside.md\n');self.denied(self.connect)
        self.instruction.write_text('Fictional governing instructions.\n')
        plugin=self.config/'plugins';plugin.mkdir();(plugin/'installed_plugins.json').write_text('{}')
        self.denied(self.connect)

    def test_private_lock_and_revoke_with_other_process_holding_shared_lock(self):
        self.approve()
        held=subprocess.Popen([sys.executable,'-c','import fcntl,os,sys; f=open(sys.argv[1]); fcntl.flock(f,fcntl.LOCK_SH); print("held",flush=True); sys.stdin.read()',str(self.registry_root/'launch.lock')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        try:
            self.assertEqual(held.stdout.readline().strip(),'held')
            start=time.monotonic();result=self.approve(revoke=True)
            self.assertLess(time.monotonic()-start,1)
            self.assertTrue(result['in_flight_launch_uncertain'])
            self.denied(self.connect)
        finally:
            held.communicate('',timeout=3)
        (self.registry_root/'operator.lock').chmod(0o644)
        with self.assertRaises(client.ClientError):self.approve()

    def test_changed_identity_exclusion_and_stale_generation_denied(self):
        self.approve()
        self.binary.write_text(self.binary.read_text()+'\n# binary changed\n');self.denied(self.connect)
        self.approve()
        self.argv[2]='changed-model';self.denied(self.connect);self.argv[2]='fixture-worker'
        path=self.registry_root/'registry.json';pristine=path.read_bytes();value=json.loads(pristine)
        value['approval']['generation']-=1;path.write_text(json.dumps(value));self.denied(self.connect)
        with self.assertRaises(client.ClientError):self.approve(revoke=True)
        path.write_bytes(pristine)  # Restore only this test's intentional corruption.
        self.approve(revoke=True)
        self.approve()
        value=json.loads(path.read_text());value['approval']['packet']['excluded']=[]
        path.write_text(json.dumps(value));self.denied(self.connect)

    def test_exact_display_bytes_rehashed_and_absences_are_observed(self):
        packet=self.packet();self.assertIsNone(packet['current'][str(self.project/'.claude/rules')])
        packet['prospective'][str(self.project/'CLAUDE.md')]['text']+='changed'
        with self.assertRaises(client.ClientError):c.validate_packet(packet)
        self.approve()
        extra=self.project/'.claude/rules';extra.mkdir(parents=True);(extra/'added.md').write_text('new rule')
        self.denied(self.connect)



    def test_missing_malformed_registry_project_replacement_and_selector_drift(self):
        self.approve()
        registry=self.registry_root/'registry.json';original=registry.read_bytes()
        for data in (b'{}',b'not-json',b'{"version":1,"generation":0,"approval":null}',b'{"version":1,"version":1}'):
            registry.write_bytes(data);self.denied(self.connect)
        registry.unlink();self.denied(self.connect);registry.write_bytes(original)
        with patch.dict(os.environ,{'CLAUDE_CONFIG_DIR':str(self.home/'different')}):self.denied(self.connect)
        self.project.rename(self.base/'original-project');self.project.mkdir()
        self.denied(self.connect)

    def test_fixed_authority_is_not_selected_by_profile_or_environment(self):
        with patch.object(c,'authority',REAL_AUTHORITY),patch.object(security,'public_directory',side_effect=security.SecurityError('unavailable')) as discovery:
            self.denied(self.connect)
        self.assertEqual(discovery.call_args.args[0],c.DISCOVERY)
        self.assertEqual(discovery.call_args.args[1],0)


class PublicSourceRaceTests(unittest.TestCase):
    def test_native_fifo_is_refused_without_blocking(self):
        with tempfile.TemporaryDirectory() as temporary:
            versions=Path(temporary).resolve()/'versions';versions.mkdir()
            fifo=versions/'2.1.319';os.mkfifo(fifo,0o700)
            code='''from memory_kit import client, context_authority as c
import sys
try: c._native([sys.argv[1]])
except client.ClientError as error:
    assert str(error)=='Native executable identity is unsafe.', str(error)
else: raise AssertionError('FIFO accepted')
'''
            result=subprocess.run([sys.executable,'-c',code,str(fifo)],capture_output=True,text=True,timeout=2)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_read_refuses_parent_replacement_and_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();parent=root/'parent';parent.mkdir()
            source=parent/'source.md';source.write_text('fictional bytes')
            real_read=os.read
            replaced=False
            def replace(fd,count):
                nonlocal replaced
                result=real_read(fd,count)
                if not replaced:
                    replaced=True
                    parent.rename(root/'retired');parent.mkdir()
                    (parent/'source.md').write_text('replacement')
                return result
            with patch.object(c.os,'read',side_effect=replace):
                with self.assertRaises((client.ClientError,OSError)):c._read(source)
            source.unlink();source.symlink_to(root/'retired/source.md')
            with self.assertRaises(client.ClientError):c._read(source)

    def test_public_inode_replacement_and_private_lock_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();source=root/'registry.json';source.write_bytes(b'{}')
            fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
            real_read=os.read
            def replace(opened,count):
                value=real_read(opened,count)
                other=root/'replacement';other.write_bytes(b'{}');os.replace(other,source)
                return value
            try:
                with patch.object(security,'_check_volume'),patch.object(security,'_check_acl'),patch.object(security.os,'read',side_effect=replace):
                    with self.assertRaises(security.SecurityError):security.public_file_at(fd,source.name,os.getuid())
            finally:os.close(fd)

    def test_native_release_resolver_observes_embedded_version_and_drift(self):
        self.assertEqual(c.SUPPORTED_CONTRACTS,
                         frozenset({'claude-code/2.1.318','claude-code/2.1.319'}))
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();versions=root/'versions';versions.mkdir()
            for version in ('2.1.318','2.1.319'):
                with self.subTest(version=version):
                    binary=versions/version
                    marker=f'README_URL:"https://code.claude.com/docs/en/overview",VERSION:"{version}"'.encode()
                    binary.write_bytes(b'\xcf\xfa\xed\xfe'+marker)
                    binary.chmod(0o700)  # New isolated fixture only.
                    result=REAL_NATIVE([str(binary),'--model','fixture'])
                    self.assertEqual(result['version'],version)
                    self.assertEqual(result['sha256'],c.digest(binary.read_bytes()))
                    other='2.1.319' if version=='2.1.318' else '2.1.318'
                    binary.write_bytes(b'\xcf\xfa\xed\xfe'+marker.replace(version.encode(),other.encode()))
                    with self.assertRaisesRegex(client.ClientError,'embedded release'):
                        REAL_NATIVE([str(binary)])

    def test_native_unknown_versions_have_no_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            versions=Path(temporary).resolve()/'versions';versions.mkdir()
            for version in ('2.1.317','2.1.320'):
                binary=versions/version
                binary.write_bytes(b'\xcf\xfa\xed\xfe'+
                    f'README_URL:"https://code.claude.com/docs/en/overview",VERSION:"{version}"'.encode())
                binary.chmod(0o700)  # New isolated fixture only.
                with self.subTest(version=version),self.assertRaisesRegex(client.ClientError,'supported'):
                    REAL_NATIVE([str(binary)])


class AuthorityDelegationTests(unittest.TestCase):
    def test_real_authority_validates_every_delegation_boundary(self):
        import types
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            root = base / 'delegated'
            discovery = base / 'discovery'
            delegation = {'version': 1, 'operator_uid': 502, 'coding_uid': 501, 'root': str(root)}
            @contextmanager
            def public_directory(path, uid, coding):
                fd = os.open(base, os.O_RDONLY | os.O_DIRECTORY)
                try: yield fd
                finally: os.close(fd)
            with patch.object(c, 'DISCOVERY', discovery), \
                 patch.object(c, '__file__', str(root / 'software/memory_kit/context_authority.py')), \
                 patch.object(security, 'public_directory', side_effect=public_directory), \
                 patch.object(c, 'read_at', side_effect=lambda *args: c.canonical(delegation)), \
                 patch('pwd.getpwuid', return_value=types.SimpleNamespace(pw_name='fictional-coder')), \
                 patch.object(security, 'standard_coding_identity', return_value={'uid': 501}) as coder, \
                 patch.object(security, 'assert_not_agent_writable'), \
                 patch('memory_kit.host._source_files', return_value=[]):
                with REAL_AUTHORITY(501) as (_, uid, software):
                    self.assertEqual(uid, 502)
                    self.assertEqual(software, c.digest(c.canonical([])))
                coder.assert_called_once_with('fictional-coder')
                cases = [{**delegation, 'extra': 1}]
                cases += [{k: v for k, v in delegation.items() if k != missing} for missing in delegation]
                cases += [{**delegation, key: value} for key, values in (
                    ('operator_uid', [500, 501, True, '502']),
                    ('coding_uid', [500, 502, True, '501']),
                    ('version', [0, 2, True]), ('root', [None, []])) for value in values]
                original = dict(delegation)
                for invalid in cases:
                    delegation.clear(); delegation.update(invalid)
                    with self.subTest(invalid=invalid), self.assertRaises(client.ClientError):
                        with REAL_AUTHORITY(501): self.fail('Invalid delegation admitted')
                delegation.clear(); delegation.update(original)
                with self.assertRaises(client.ClientError):
                    with REAL_AUTHORITY(503): self.fail('Wrong coding UID admitted')


if __name__=="__main__":unittest.main()
