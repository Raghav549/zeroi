class ZeroiError(Exception):
    pass


class PlanningError(ZeroiError):
    pass


class ExecutionError(ZeroiError):
    pass


class SecurityError(ZeroiError):
    pass


class RecoveryError(ZeroiError):
    pass


class DeviceError(ZeroiError):
    pass


class ArtifactError(ZeroiError):
    pass
