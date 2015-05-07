import os

import types_pb2 as types
import messages_pb2 as proto
import storage_pb2 as proto_storage
from bip32 import BIP32, DerivationCache
import tools
import signing
import coindef
import binascii
from mnemonic import Mnemonic
from pbkdf2 import PBKDF2
import hmac
import pyaes
import hashlib

class NotInitializedException(Exception):
    pass

class Session(object):
    def __init__(self):
        self.node = None
        self.passphrase = None
        self.pin = ''

    def has_node(self):
        # Node is already cached
        return self.node != None

    def has_passphrase(self):
        # Passphrase is already set
        return self.passphrase != None

    def get_passphrase(self):
        if self.passphrase == None:
            return u''
        return self.passphrase

    def set_passphrase(self, passphrase):
        # Drop cached node, next get_node will generate fresh one
        self.passphrase = passphrase
        self.node = None

    def set_node(self, node):
        self.node = types.HDNodeType()
        self.node.CopyFrom(node)

    def set_pin(self, pin):
        self.pin = pin

class Storage(object):
    def __init__(self, filename, bootloader_mode=False):
        self.vendor = 'bitcointrezor.com'
        self.major_version = 1
        self.minor_version = 0
        self.patch_version = 0

        self.storage_version = 1  # Version of wallet file

        self.default_settings = proto_storage.Storage(
            version=self.storage_version,
            language='english',
        )

        self.device_id_filename = os.path.expanduser('~/.trezor')
        self._init_device_id()

        self.bootloader_mode = bootloader_mode
        self.filename = filename
        self.load()  # Storage protobuf object

        self.init_session()

    def init_session(self):
        self.session = Session()
        DerivationCache.clear()

    def get_features(self):
        m = proto.Features()
        m.vendor = self.vendor
        m.major_version = self.major_version
        m.minor_version = self.minor_version
        m.patch_version = self.patch_version
        m.bootloader_mode = self.bootloader_mode
        
        m.device_id = self.get_device_id()
        
        m.pin_protection = bool(self.struct.pin != '')
        m.passphrase_protection = self.get_passphrase_protection()
        m.language = self.struct.language
        m.label = self.struct.label
        m.initialized = bool(self.is_initialized())
        m.imported = bool(self.struct.imported)
        
        # Add all known coin
        types = coindef.types.keys()
        types.sort()
        for t in types:
            coin = m.coins.add()
            coin.CopyFrom(coindef.types[t])
            
        return m

    def _init_device_id(self):
        device_id_len = 12
        if os.path.exists(self.device_id_filename) and \
           os.path.getsize(self.device_id_filename) == device_id_len:
            return

        print "Generating new device serial number..."
        f = open(self.device_id_filename, 'w')
        f.write(os.urandom(device_id_len))
        f.close()

    def _refresh_device_id(self):
        os.unlink(self.device_id_filename)
        self._init_device_id()

    def get_device_id(self):
        f = open(self.device_id_filename, 'r')
        sernum = f.read()
        f.close()
        return binascii.hexlify(sernum).upper()
        
    def check_struct(self, struct):
        # Check if protobuf struct loaded from local storage
        # is compatible with current codebase.

        # Stub for wallet format updates
        if struct.version != 1:
            raise IOError("Incompatible wallet file, creating new one")

    def load(self):
        try:
            struct = proto_storage.Storage()
            struct.ParseFromString(open(self.filename, 'r').read())

            # Update to newer version or raises IOError if not possible
            self.check_struct(struct)
            self.struct = struct

        except:
            print "Wallet load failed, creating new one"
            self.struct = proto_storage.Storage()
            self.struct.CopyFrom(self.default_settings)
            self.save()

    def get_pin(self):
        return self.struct.pin

    def get_passphrase_protection(self):
        return bool(self.struct.passphrase_protection)

    def get_homescreen(self):
        return self.struct.homescreen

    def set_passphrase_protection(self, passphrase_protection):
        self.struct.passphrase_protection = passphrase_protection
        self.save()

    def set_homescreen(self, homescreen):
        if len(homescreen) == 1024:
            self.struct.homescreen = homescreen
        else:
            self.struct.ClearField('homescreen')
        self.save()

    def set_secret(self, language, passphrase_protection, mnemonic=None, node=None, skip_checksum=False):
        '''This should be the only method which *set* mnemonic or node'''
        if node != None and node.IsInitialized():
            self.struct.passphrase_protection = bool(passphrase_protection)
            self.struct.node.CopyFrom(node)
            self.struct.ClearField('mnemonic')
        elif mnemonic != '':
            if not skip_checksum and not Mnemonic(language).check(mnemonic):
                raise Exception("Invalid mnemonic")
            self.struct.passphrase_protection = bool(passphrase_protection)
            self.struct.mnemonic = mnemonic
            self.struct.ClearField('node')

        # Device ID is changing with every secrets change
        # to improve privacy and un-traceability of the device
        self._refresh_device_id()

        self.init_session()
        self.save()        

    def get_label(self):
        return self.struct.label

    def set_label(self, label):
        self.struct.label = label
        self.save()

    def get_languages(self):
        return ['english']

    def set_language(self, language):
        if language in self.get_languages():
            self.struct.language = language
        else:
            raise Exception("Unsupported language")
        self.save()

    def set_imported(self, imported):
        self.struct.imported = imported
        self.save()

    def is_initialized(self):
        if self.struct.HasField('mnemonic'):
            return True
        if self.struct.HasField('node'):
            return True
        return False
    
    def is_locked(self):
        '''Return False if mnemonic/node is locked by passphrase, so
        get_node() will fail.'''

        if not self.get_passphrase_protection():
            return False

        if self.session.has_passphrase():
            return False

        return True

    def is_authorized(self):
        '''Return False if PIN has not been entered in this session'''
        if self.get_pin() == self.session.pin:
            return True

        return False

    def authorize(self, pin):
        if self.get_pin() == pin:
            self.session.set_pin(pin)

        return self.is_authorized()

    def unlock(self, passphrase):
        self.session.set_passphrase(passphrase)

    def get_node(self):
        '''Return decrypted HDNodeType (from stored mnemonic or encrypted HDNodeType)'''
        if not self.is_initialized():
            raise NotInitializedException("Device not initalized")

        if self.is_locked():
            raise Exception("Passphrase required")

        if self.struct.HasField('mnemonic') and self.struct.HasField('node'):
            raise Exception("Cannot have both mnemonic and node at the same time")

        if self.session.has_node():
            # If we've already unlocked node, let's use it
            return self.session.node

        if self.struct.HasField('mnemonic'):
            print "Loading mnemonic"
            seed = Mnemonic(self.struct.language).to_seed(self.struct.mnemonic, passphrase=self.session.get_passphrase())
            self.session.set_node(BIP32.get_node_from_seed(seed))
        else:
            print "Loading node"
            passphrase = self.session.get_passphrase()
            if passphrase:
                secret = PBKDF2(passphrase, "TREZORHD", iterations=2048, macmodule=hmac, digestmodule=hashlib.sha512).read(64)
                node = types.HDNodeType()
                node.CopyFrom(self.struct.node)
                aes_key = secret[:32]
                aes_iv = secret[32:48]
                aescbc = pyaes.AESModeOfOperationCBC(key=aes_key, iv=aes_iv)
                node.chain_code = aescbc.decrypt(node.chain_code[:16]) + aescbc.decrypt(node.chain_code[16:])
                node.private_key = aescbc.decrypt(node.private_key[:16]) + aescbc.decrypt(node.private_key[16:])
                self.session.set_node(node)
            else:
                self.session.set_node(self.struct.node)

        return self.session.node

    def set_pin(self, pin):
        self.struct.pin = pin
        self.save()

        # Drop cached PIN
        self.init_session()

    def increase_pin_attempt(self):
        self.struct.pin_failed_attempts += 1
        self.save()

    def clear_pin_attempt(self):
        self.struct.pin_failed_attempts = 0
        self.save()

    def get_pin_delay(self):
        if self.struct.pin_failed_attempts:
            return 1.8 ** self.struct.pin_failed_attempts
        return 0

    def save(self):
        open(self.filename, 'w').write(self.struct.SerializeToString())

    def wipe_device(self):
        os.unlink(self.filename)
        self._refresh_device_id()
        self.load()

        if self.struct.HasField('mnemonic') or self.struct.HasField('node'):
            raise Exception("Unexpected state")
        print self.get_features()

    def load_device(self, mnemonic, node, language, label, pin, passphrase_protection, skip_checksum=False):
        self.set_secret(language=language, mnemonic=mnemonic, skip_checksum=skip_checksum,
                        node=node, passphrase_protection=passphrase_protection)
        self.set_language(language)
        self.set_label(label)
        self.set_pin(pin)

        # Device has new secrets, which are known to potential attacker already
        self.clear_pin_attempt()

        self.save()
        self.init_session()
