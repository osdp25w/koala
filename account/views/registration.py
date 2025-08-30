import logging

from django.contrib.auth.models import User
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny

from account.models import Member, RBACRole
from account.serializers import MemberDetailSerializer, MemberRegistrationSerializer
from utils.response import APIFailedResponse, APISuccessResponse
from utils.views import BaseGenericViewSet


class MemberRegistrationViewSet(mixins.CreateModelMixin, BaseGenericViewSet):
    queryset = Member.objects.none()
    serializer_class = MemberRegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        """創建新會員帳號"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # 創建會員
            member = serializer.save()

            # 自動分配默認角色
            self._assign_default_role(member)

            # 返回創建成功的會員資訊
            response_serializer = MemberDetailSerializer(
                member, context=self.get_serializer_context()
            )

            return APISuccessResponse(
                data=response_serializer.data,
                message='註冊成功！歡迎加入',
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return APIFailedResponse(
                message=f"註冊失敗：{str(e)}", status=status.HTTP_400_BAD_REQUEST
            )

    def _assign_default_role(self, member):
        """為新註冊會員分配默認角色"""
        try:
            # 根據會員類型分配對應角色
            if member.type == Member.TYPE_TOURIST:
                role_name = 'tourist_role'
            elif member.type == Member.TYPE_REAL:
                role_name = 'real_member_role'
            else:
                role_name = 'tourist_role'  # 默認為觀光客角色

            default_role = RBACRole.objects.filter(
                name=role_name, is_staff_only=False
            ).first()

            if default_role:
                member.rbac_roles.add(default_role)

        except Exception as e:
            # 記錄錯誤但不影響註冊流程
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Failed to assign default role to member {member.username}: {e}"
            )

    @action(detail=False, methods=['GET'], url_path='check-availability')
    def check_availability(self, request):
        """檢查信箱是否可用"""
        email = request.data.get('email')

        result = {
            'available': True,
        }

        if email:
            if User.objects.filter(email=email).exists():
                result['available'] = False

        return APISuccessResponse(data=result)
