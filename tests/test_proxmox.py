from mock import patch, MagicMock
import pytest

from virtwho.virt.proxmox.proxmox import Proxmox, ProxmoxConfigSection
from virtwho.virt import Guest, Hypervisor
from virtwho.config import VirtConfigSection

class TestProxmoxConfigSection:
    def test_required_fields(self):
        # Missing server
        section = ProxmoxConfigSection("test-proxmox", None)
        section.update({'username': 'user', 'password': 'pw'})
        with pytest.raises(KeyError):
            _ = section['server']

        # Missing username
        section = ProxmoxConfigSection("test-proxmox", None)
        section.update({'server': 'host', 'password': 'pw'})
        with pytest.raises(KeyError):
            _ = section['username']

        # Missing password
        section = ProxmoxConfigSection("test-proxmox", None)
        section.update({'server': 'host', 'username': 'user'})
        with pytest.raises(KeyError):
            _ = section['password']

        # All present
        section = ProxmoxConfigSection("test-proxmox", None)
        section.update({'server': 'host', 'username': 'user', 'password': 'pw'})
        assert section['server'] == 'host'
        assert section['username'] == 'user'
        assert section['password'] == 'pw'

    @patch('virtwho.config.Password')
    def test_encrypted_password(self, mock_Password):
        # Simulate decryption
        mock_Password.return_value.decrypt.return_value = 'decrypted_pw'
        config = {
            'server': 'host',
            'username': 'user',
            'encrypted_password': 'deadbeef'
        }
        section = ProxmoxConfigSection(MagicMock(), config)
        # Should raise KeyError because password is not set by config section logic
        with pytest.raises(KeyError):
            _ = section['password']

    def test_default_realm(self):
        section = ProxmoxConfigSection(MagicMock(), {'server': 'host', 'username': 'user', 'password': 'pw'})
        assert section['realm'] == 'pam'
        # Custom realm is not supported by config section logic, so should still be 'pam'
        section2 = ProxmoxConfigSection(MagicMock(), {'server': 'host', 'username': 'user', 'password': 'pw', 'realm': 'custom'})
        assert section2['realm'] == 'pam'

class TestProxmoxBackend:
    @patch('virtwho.virt.proxmox.proxmox.requests.post')
    def test_authenticate_success(self, mock_post):
        # Mock successful response
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            'data': {
                'ticket': 'ticket123',
                'CSRFPreventionToken': 'csrf456'
            }
        }
        mock_resp.raise_for_status = lambda: None
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        config = {'server': 'host', 'username': 'user', 'password': 'pw'}
        logger = MagicMock()
        proxmox = Proxmox(logger, config, dest=None)
        proxmox.authenticate()
        assert proxmox.ticket == 'ticket123'
        assert proxmox.csrf_token == 'csrf456'

    @patch('virtwho.virt.proxmox.proxmox.requests.post')
    def test_authenticate_failure(self, mock_post):
        # Mock failed response
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("Auth failed")
        mock_resp.status_code = 500
        mock_post.return_value = mock_resp

        config = {'server': 'host', 'username': 'user', 'password': 'pw'}
        logger = MagicMock()
        proxmox = Proxmox(logger, config, dest=None)
        with pytest.raises(Exception):
            proxmox.authenticate()

    @patch('virtwho.virt.proxmox.proxmox.requests.get')
    @patch.object(Proxmox, 'authenticate')
    def test_getHostGuestMapping(self, mock_auth, mock_get):
        # Simulate Proxmox API responses for nodes, qemu, lxc
        def side_effect(url, *args, **kwargs):
            if url.endswith('/nodes'):
                resp = MagicMock()
                resp.json.return_value = {'data': [{'node': 'n1'}, {'node': 'n2'}]}
                resp.raise_for_status = lambda: None
                resp.status_code = 200
                return resp
            elif url.endswith('/nodes/n1/qemu'):
                resp = MagicMock()
                resp.json.return_value = {'data': [{'vmid': '101', 'name': 'vm1', 'status': 'running'}]}
                resp.raise_for_status = lambda: None
                resp.status_code = 200
                return resp
            elif url.endswith('/nodes/n2/lxc'):
                resp = MagicMock()
                resp.json.return_value = {'data': [{'vmid': '201', 'name': 'ct1', 'status': 'running'}]}
                resp.raise_for_status = lambda: None
                resp.status_code = 200
                return resp
            else:
                resp = MagicMock()
                resp.json.return_value = {'data': []}
                resp.raise_for_status = lambda: None
                resp.status_code = 200
                return resp

        mock_get.side_effect = side_effect

        config = {'server': 'host', 'username': 'user', 'password': 'pw'}
        logger = MagicMock()
        proxmox = Proxmox(logger, config, dest=None)
        mapping = proxmox.getHostGuestMapping()
        # Should contain both qemu and lxc guests
        assert isinstance(mapping, dict)
        assert any('101' in str(v) for v in mapping.values())
        assert any('201' in str(v) for v in mapping.values())

    @patch.object(Proxmox, 'authenticate')
    def test_statusConfirmConnection(self, mock_auth):
        config = {'server': 'host', 'username': 'user', 'password': 'pw'}
        logger = MagicMock()
        proxmox = Proxmox(logger, config, dest=None)
        proxmox.statusConfirmConnection()
        assert mock_auth.called