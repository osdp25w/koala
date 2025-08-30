from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from account.jwt import JWTService
from account.serializers import (
    LoginResponseSerializer,
    LoginSerializer,
    RefreshTokenSerializer,
)
from utils.constants import ResponseCode, ResponseMessage
from utils.response import APIFailedResponse, APISuccessResponse


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return APIFailedResponse(
            code=ResponseCode.VALIDATION_ERROR,
            msg=ResponseMessage.VALIDATION_ERROR,
            data=serializer.errors,
        )

    email = serializer.validated_data['email']
    password = serializer.validated_data['password']

    profile = JWTService.authenticate_user(email, password)
    if not profile:
        return APIFailedResponse(
            code=ResponseCode.USER_NOT_FOUND,
            msg=ResponseMessage.USER_NOT_FOUND,
            details={'email': email},
        )

    tokens = JWTService.create_tokens(profile)

    response_data = {
        'tokens': tokens,
        'profile': {
            'id': profile.id,
            'email': profile.email,
            'username': profile.username,
            'profile_type': profile._meta.model_name,
            'is_active': profile.is_active,
        },
    }

    response_serializer = LoginResponseSerializer(data=response_data)
    response_serializer.is_valid(raise_exception=True)

    return APISuccessResponse(
        data=response_serializer.data, msg=ResponseMessage.SUCCESS
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token_view(request):
    try:
        serializer = RefreshTokenSerializer(data=request.data)
        if not serializer.is_valid():
            return APIFailedResponse(
                code=ResponseCode.VALIDATION_ERROR,
                msg=ResponseMessage.VALIDATION_ERROR,
            )

        refresh_token = serializer.validated_data['refresh_token']

        result = JWTService.refresh_access_token(refresh_token)
        if not result:
            return APIFailedResponse(
                code=ResponseCode.UNAUTHORIZED, msg=ResponseMessage.UNAUTHORIZED
            )

        return APISuccessResponse(data={'tokens': result}, msg=ResponseMessage.SUCCESS)

    except Exception as e:
        return APIFailedResponse(
            code=ResponseCode.UNAUTHORIZED,
            msg=ResponseMessage.UNAUTHORIZED,
            details={'error': str(e)},
        )


@api_view(['POST'])
def logout_view(request):
    try:
        # 在實際應用中，你可能需要將 refresh_token 加入黑名單
        # 這裡只是簡單的登出回應

        return APISuccessResponse(msg=ResponseMessage.SUCCESS)

    except Exception as e:
        return APIFailedResponse(
            code=ResponseCode.INTERNAL_ERROR,
            msg=ResponseMessage.INTERNAL_ERROR,
            details={'error': str(e)},
        )
