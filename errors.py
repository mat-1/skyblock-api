class SkyBlockError(Exception): pass
class InvalidUUID(SkyBlockError): pass
class InvalidUser(SkyBlockError): pass
class InvalidItem(SkyBlockError): pass
class ThrottleError(SkyBlockError): pass
