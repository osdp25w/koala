from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from account.models import Member, Staff

JWT_EXPIRES_IN = 60 * 60 * 24


class JWTService:
    @staticmethod
    def authenticate_user(email: str, password: str):
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return None

        authenticated_user = authenticate(username=user.username, password=password)
        if not authenticated_user:
            return None

        try:
            profile = user.profile
            if not profile or not profile.is_active:
                return None
            return profile
        except (Member.DoesNotExist, Staff.DoesNotExist):
            return None

    @staticmethod
    def create_tokens(profile):
        user = profile.user

        refresh = RefreshToken.for_user(user)

        # refresh['user_id'] = user.id
        # refresh['profile_type'] = profile._meta.model_name
        # refresh['is_active'] = profile.is_active

        # # 根據用戶類型添加特定資訊
        # if isinstance(profile, Member):
        #     refresh['member_type'] = profile.type
        # elif isinstance(profile, Staff):
        #     refresh['staff_type'] = profile.type

        return {
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'token_type': 'Bearer',
            'expires_in': JWT_EXPIRES_IN,
        }

    @staticmethod
    def refresh_access_token(refresh_token):
        try:
            refresh = RefreshToken(refresh_token)
            access_token = refresh.access_token

            return {
                'access_token': str(access_token),
                'token_type': 'Bearer',
                'expires_in': JWT_EXPIRES_IN,
            }
        except Exception:
            return None

    @staticmethod
    def validate_token(token):
        try:
            access_token = AccessToken(token)

            # 從 token 中取得 user_id
            user_id = access_token['user_id']
            user = User.objects.get(id=user_id)

            profile = user.profile
            if not profile or not profile.is_active:
                return False, '用戶已被停用'
            return True, profile

        except Exception as e:
            return False, f"無效的 token: {str(e)}"


class JWTAuthentication(authentication.BaseAuthentication):
    """自定義 JWT 認證類"""

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if not auth_header.startswith('Bearer '):
            return None

        token = auth_header.split(' ')[1]

        try:
            is_valid, result = JWTService.validate_token(token)

            if not is_valid:
                raise AuthenticationFailed(result)

            profile = result
            return (profile.user, token)

        except Exception as e:
            raise AuthenticationFailed(f'Authentication failed: {str(e)}')

    def authenticate_header(self, request):
        return 'Bearer'
