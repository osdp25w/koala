class RowAccessLevel:
    """欄位存取權限級別常數"""

    NONE = 0  # 無權限
    OWN = 1  # 只能存取自己的資料
    PROFILE_HIERARCHY = 2  # 角色範圍內的資料
    ALL = 3  # 所有資料

    CHOICES = [
        (NONE, 'No Access'),
        (OWN, 'Own Records Only'),
        (PROFILE_HIERARCHY, 'Profile Hierarchy'),
        (ALL, 'All Records'),
    ]

    @classmethod
    def from_string(cls, access_string: str) -> int:
        """將字串轉換為數值"""
        mapping = {
            'none': cls.NONE,
            'own': cls.OWN,
            'profile_hierarchy': cls.PROFILE_HIERARCHY,
            'all': cls.ALL,
        }
        return mapping.get(access_string.lower(), cls.NONE)

    @classmethod
    def to_string(cls, access_level: int) -> str:
        """將數值轉換為字串"""
        mapping = {
            cls.NONE: 'none',
            cls.OWN: 'own',
            cls.PROFILE_HIERARCHY: 'profile_hierarchy',
            cls.ALL: 'all',
        }
        return mapping.get(access_level, 'none')


class ResponseCode:
    # 1000–1999 系統層級／通用回應
    # 2000–2999 成功／一般操作
    # 3000–3999 驗證 & 授權（Authentication）
    # 4000–4999 用戶請求錯誤（Client Error）
    # 5000–5999 伺服器錯誤（Server Error）
    # 6000–6999 外部服務錯誤／第三方 API

    SUCCESS = 2000  # Operation completed successfully

    UNAUTHORIZED = 3000  # Authentication failed or credentials invalid
    TOKEN_EXPIRED = 3001  # JWT token has expired
    PERMISSION_DENIED = 3002  # User lacks required permissions

    VALIDATION_ERROR = 4000  # Request data validation failed
    METHOD_NOT_ALLOWED = 4001  # HTTP method not supported
    NOT_FOUND = 4002  # Requested resource not found
    USER_NOT_FOUND = 4003  # Specific user not found
    MEMBER_NOT_FOUND = 4004  # Member not found by email/phone
    MULTIPLE_MEMBERS_FOUND = 4005  # Multiple members found with same email/phone
    CONFLICT = 4009  # Data conflict or duplicate entry

    # Bike rental related errors
    BIKE_NOT_AVAILABLE = 4010  # Bike is not available for rent
    MEMBER_ALREADY_HAS_BIKE = 4011  # Member already has a rented bike
    BIKE_NOT_RENTED_BY_MEMBER = 4012  # Member trying to return a bike they didn't rent
    INVALID_RENTAL_ACTION = 4013  # Invalid rental action provided

    FORBIDDEN = 4030  # Access forbidden
    UNKNOWN_ERROR = 4999  # Unhandled client error

    INTERNAL_ERROR = 5000  # Server internal error

    EXTERNAL_API_ERROR = 6000  # Third-party API error
    EXTERNAL_API_AUTHORIZATION_ERROR = 6001  # Third-party API auth error
    EXTERNAL_API_ACCESS_TOKEN_NOT_FOUND = 6002  # Third-party API token missing


class ResponseMessage:
    SUCCESS = 'success'  # General success message

    UNAUTHORIZED = 'unauthorized'  # Authentication failed
    TOKEN_EXPIRED = 'token expired'  # JWT token expired
    PERMISSION_DENIED = 'permission denied'  # Insufficient permissions

    VALIDATION_ERROR = 'validation error'  # Input validation failed
    METHOD_NOT_ALLOWED = 'method not allowed'  # HTTP method not supported
    NOT_FOUND = 'resource not found'  # Resource does not exist
    USER_NOT_FOUND = 'user not found'  # User does not exist
    MEMBER_NOT_FOUND = 'member not found'  # Member not found by email/phone
    MULTIPLE_MEMBERS_FOUND = (
        'multiple members found'  # Multiple members found with same email/phone
    )
    CONFLICT = 'data conflict'  # Data conflict or duplicate

    # Bike rental related messages
    BIKE_NOT_AVAILABLE = 'bike not available for rent'
    MEMBER_ALREADY_HAS_BIKE = 'member already has a rented bike'
    BIKE_NOT_RENTED_BY_MEMBER = 'bike not rented by this member'
    INVALID_RENTAL_ACTION = 'invalid rental action'

    FORBIDDEN = 'forbidden'  # Access forbidden
    UNKNOWN_ERROR = 'request failed'  # Unhandled error

    INTERNAL_ERROR = 'internal error'  # Server internal error

    EXTERNAL_API_ERROR = 'external api error'  # Third-party API error
    EXTERNAL_API_AUTHORIZATION_ERROR = (
        'external api authorization error'  # Third-party API auth error
    )
    EXTERNAL_API_ACCESS_TOKEN_NOT_FOUND = (
        'external api access_token not found'  # Third-party API token missing
    )


class HTTPMethod:
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    PATCH = 'PATCH'
    DELETE = 'DELETE'
    HEAD = 'HEAD'
    OPTIONS = 'OPTIONS'


class ViewSetAction:
    LIST = 'list'  # GET
    RETRIEVE = 'retrieve'  # GET
    CREATE = 'create'  # POST
    UPDATE = 'update'  # PUT
    PARTIAL_UPDATE = 'partial_update'  # PATCH
    DELETE = 'delete'  # DELETE
