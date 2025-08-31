import logging

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.dispatch import receiver

from account.caches import PermissionCache
from account.models import (
    Member,
    RBACModelPermissionScope,
    RBACPermission,
    RBACRole,
    Staff,
)
from account.utils import RBACPermissionBitMapService

logger = logging.getLogger(__name__)


@receiver([post_save, post_delete], sender=RBACModelPermissionScope)
def clear_scope_related_cache(sender, instance, **kwargs):
    """當 RBACModelPermissionScope 變更時，清除相關快取"""
    # 清除該 model 的所有權限快取
    if instance.related_model:
        model_class = instance.related_model.model_class()
        if model_class:
            PermissionCache.clear_model_cache(model_class)
            # 更新該 model 的欄位映射
            RBACPermissionBitMapService.update_field_map(model_class)
            logger.info(
                f"Cleared cache for model {model_class._meta.model_name} due to scope change"
            )


@receiver([post_save, post_delete], sender=RBACPermission)
def clear_permission_related_cache(sender, instance, **kwargs):
    """當 RBACPermission 變更時，清除相關快取"""
    # 清除該 scope 對應 model 的所有權限快取
    if instance.scope and instance.scope.related_model:
        model_class = instance.scope.related_model.model_class()
        if model_class:
            PermissionCache.clear_model_cache(model_class)
            logger.info(
                f"Cleared cache for model {model_class._meta.model_name} due to permission change"
            )


@receiver(m2m_changed, sender=RBACRole.permissions.through)
def clear_role_permission_cache(sender, instance, action, pk_set, **kwargs):
    """當 RBACRole 的 permissions 變更時，清除相關快取"""
    if action in ['post_add', 'post_remove', 'post_clear']:
        # 獲取所有使用此 role 的用戶
        affected_members = instance.member_profiles.all()
        affected_staff = instance.staff_profiles.all()

        # 清除所有相關用戶的快取
        for profile in affected_members:
            PermissionCache.clear_profile_cache(profile)

        for profile in affected_staff:
            PermissionCache.clear_profile_cache(profile)

        logger.info(f"Cleared cache for all users with role {instance.name}")


@receiver(m2m_changed, sender=Member.rbac_roles.through)
def clear_member_role_cache(sender, instance, action, **kwargs):
    """當 Member 的 rbac_roles 變更時，清除該用戶快取"""
    if action in ['post_add', 'post_remove', 'post_clear']:
        PermissionCache.clear_profile_cache(instance)
        logger.info(f"Cleared cache for member {instance.username}")


@receiver(m2m_changed, sender=Staff.rbac_roles.through)
def clear_staff_role_cache(sender, instance, action, **kwargs):
    """當 Staff 的 rbac_roles 變更時，清除該用戶快取"""
    if action in ['post_add', 'post_remove', 'post_clear']:
        PermissionCache.clear_profile_cache(instance)
        logger.info(f"Cleared cache for staff {instance.username}")


@receiver([post_save, post_delete], sender=Member)
def clear_member_cache(sender, instance, signal, **kwargs):
    """當 Member 新增/刪除時，清除快取"""
    if kwargs.get('created') or signal == post_delete:
        PermissionCache.clear_profile_cache(instance)


@receiver([post_save, post_delete], sender=Staff)
def clear_staff_cache(sender, instance, signal, **kwargs):
    """當 Staff 新增/刪除時，清除快取"""
    if kwargs.get('created') or signal == post_delete:
        PermissionCache.clear_profile_cache(instance)


@receiver(pre_save, sender=Member)
@receiver(pre_save, sender=Staff)
def sync_profile_data_before_save(sender, instance, **kwargs):
    """當 Member/Staff 保存前，進行雙向資料同步"""
    if hasattr(instance, 'user') and instance.user:
        # 檢查 Profile 是否有更新，如果有則同步到 User
        if instance.pk:
            try:
                old_instance = sender.objects.get(pk=instance.pk)
                user_needs_update = False

                if old_instance.username != instance.username:
                    instance.user.username = instance.username
                    user_needs_update = True
                if old_instance.email != instance.email:
                    instance.user.email = instance.email
                    user_needs_update = True

                if user_needs_update:
                    instance.user.save(update_fields=['username', 'email'])
                    logger.debug(
                        f"Synced {sender.__name__} changes to User {instance.username}"
                    )

            except sender.DoesNotExist:
                # 新建的情況，從 User 同步到 Profile
                instance.username = instance.user.username
                instance.email = instance.user.email
                logger.debug(
                    f"Synced User data to new {sender.__name__} {instance.username}"
                )
        else:
            # 新建的情況，從 User 同步到 Profile
            instance.username = instance.user.username
            instance.email = instance.user.email
            logger.debug(
                f"Synced User data to new {sender.__name__} {instance.username}"
            )


@receiver(post_save, sender=User)
def sync_user_profile_data(sender, instance, **kwargs):
    """當 User 更新時，同步更新相關的 Profile 資料"""
    profile = instance.profile
    if profile:
        # 檢查是否需要更新
        if profile.username != instance.username or profile.email != instance.email:
            profile.username = instance.username
            profile.email = instance.email
            profile.save()
            logger.info(
                f"Synced {profile.__class__.__name__} profile for user {instance.username}"
            )


@receiver(post_delete, sender=Member)
def delete_member_user(sender, instance, **kwargs):
    """當 Member 被刪除時，自動刪除對應的 Django User"""
    if instance.user:
        try:
            instance.user.delete()
            logger.info(
                f"Deleted User {instance.user.username} when Member profile was deleted"
            )
        except Exception as e:
            logger.error(f"Failed to delete User {instance.user.username}: {e}")


@receiver(post_delete, sender=Staff)
def delete_staff_user(sender, instance, **kwargs):
    """當 Staff 被刪除時，自動刪除對應的 Django User"""
    if instance.user:
        try:
            instance.user.delete()
            logger.info(
                f"Deleted User {instance.user.username} when Staff profile was deleted"
            )
        except Exception as e:
            logger.error(f"Failed to delete User {instance.user.username}: {e}")


# 當任何 model 結構變更時，更新欄位映射
def update_model_field_maps():
    """更新所有 model 的欄位映射（在 migration 或 model 變更後調用）"""
    from django.apps import apps

    # 獲取所有有 RBACModelPermissionScope 的 model
    content_types = ContentType.objects.filter(
        rbacmodelpermissionscope__isnull=False
    ).distinct()

    for content_type in content_types:
        model_class = content_type.model_class()
        if model_class:
            RBACPermissionBitMapService.update_field_map(model_class)
            logger.info(f"Updated field map for {model_class._meta.model_name}")
