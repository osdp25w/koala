from django.db.models import Q
from django.utils import timezone
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers

from account.models import Member
from bike.models import BikeInfo, BikeRealtimeStatus
from rental.constants import RentalActionOption
from rental.models import BikeRental
from utils.constants import ResponseCode, ResponseMessage


class BikeInfoSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = BikeInfo
        fields = ['bike_id', 'bike_name', 'bike_model']


class MemberSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ['id', 'full_name', 'phone']


class BikeRentalListSerializer(serializers.ModelSerializer):
    bike = BikeInfoSimpleSerializer(read_only=True)
    member = MemberSimpleSerializer(read_only=True)
    duration_minutes = serializers.ReadOnlyField(source='get_duration_minutes')

    class Meta:
        model = BikeRental
        fields = [
            'id',
            'bike',
            'member',
            'start_time',
            'end_time',
            'rental_status',
            'pickup_location',
            'return_location',
            'total_fee',
            'duration_minutes',
            'created_at',
        ]


class BikeRentalDetailSerializer(serializers.ModelSerializer):
    bike = BikeInfoSimpleSerializer(read_only=True)
    member = MemberSimpleSerializer(read_only=True)
    duration_minutes = serializers.ReadOnlyField(source='get_duration_minutes')

    class Meta:
        model = BikeRental
        fields = [
            'id',
            'bike',
            'member',
            'start_time',
            'end_time',
            'rental_status',
            'pickup_location',
            'return_location',
            'total_fee',
            'memo',
            'duration_minutes',
            'created_at',
            'updated_at',
        ]


class BikeRentalMemberCreateSerializer(serializers.ModelSerializer):
    bike_id = serializers.CharField(write_only=True)
    bike = BikeInfoSimpleSerializer(read_only=True)
    member = MemberSimpleSerializer(read_only=True)

    class Meta:
        model = BikeRental
        fields = [
            'bike_id',  # write_only 欄位
            'id',
            'bike',
            'member',
            'start_time',
            'rental_status',
            'created_at',  # 回傳欄位
        ]
        read_only_fields = ['id', 'start_time', 'rental_status', 'created_at']

    def validate_bike_id(self, value):
        try:
            bike = BikeInfo.objects.get(bike_id=value)
        except BikeInfo.DoesNotExist:
            raise serializers.ValidationError('Bike not found')

        # 檢查車輛即時狀態是否可租借
        try:
            realtime_status = bike.realtime_status
            if realtime_status.status != BikeRealtimeStatus.StatusOptions.IDLE:
                raise serializers.ValidationError('Bike is not available for rental')
        except BikeRealtimeStatus.DoesNotExist:
            raise serializers.ValidationError('Bike realtime status not found')

        return value

    def validate(self, attrs):
        user = self.context['request'].user
        member = user.profile

        # 檢查會員是否已有進行中的租借
        if hasattr(member, 'bike_realtime_status') and member.bike_realtime_status:
            raise serializers.ValidationError('You already have an active rental')

        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        member = user.profile
        bike_id = validated_data.pop('bike_id')
        bike = BikeInfo.objects.get(bike_id=bike_id)

        rental = BikeRental.objects.create(
            member=member,
            bike=bike,
            start_time=timezone.now(),
            rental_status=BikeRental.RentalStatusOptions.ACTIVE,
            **validated_data
        )

        # 同步更新車輛即時狀態
        realtime_status = bike.realtime_status
        realtime_status.status = BikeRealtimeStatus.StatusOptions.RENTED
        realtime_status.current_member = member
        realtime_status.save()

        return rental


class BikeRentalMemberUpdateSerializer(serializers.ModelSerializer):
    action = serializers.ChoiceField(
        choices=RentalActionOption.choices, write_only=True
    )
    bike = BikeInfoSimpleSerializer(read_only=True)
    member = MemberSimpleSerializer(read_only=True)
    duration_minutes = serializers.ReadOnlyField(source='get_duration_minutes')

    class Meta:
        model = BikeRental
        fields = [
            'action',  # write_only 欄位
            'id',
            'bike',
            'member',
            'start_time',
            'end_time',
            'rental_status',
            'total_fee',
            'duration_minutes',
            'updated_at',  # 回傳欄位
        ]

    def validate(self, attrs):
        user = self.context['request'].user
        member = user.profile

        # 檢查是否為該會員的租借記錄
        if self.instance.member != member:
            raise serializers.ValidationError('You can only return your own rentals')

        # 檢查租借狀態
        if self.instance.rental_status != BikeRental.RentalStatusOptions.ACTIVE:
            raise serializers.ValidationError('This rental is not active')

        return attrs

    def update(self, instance, validated_data):
        action = validated_data.pop('action')

        if action == RentalActionOption.RETURN:
            instance.end_time = timezone.now()
            instance.rental_status = BikeRental.RentalStatusOptions.COMPLETED
            instance.save()

            # 同步更新車輛即時狀態
            realtime_status = instance.bike.realtime_status
            realtime_status.status = BikeRealtimeStatus.StatusOptions.IDLE
            realtime_status.current_member = None
            realtime_status.save()

        return instance


class BikeRentalStaffCreateSerializer(serializers.ModelSerializer):
    bike_id = serializers.CharField(write_only=True)
    member_email = serializers.EmailField(write_only=True, required=False)
    member_phone = PhoneNumberField(write_only=True, required=False)
    bike = BikeInfoSimpleSerializer(read_only=True)
    member = MemberSimpleSerializer(read_only=True)

    class Meta:
        model = BikeRental
        fields = [
            'bike_id',
            'member_email',
            'member_phone',  # write_only 欄位
            'id',
            'bike',
            'member',
            'start_time',
            'rental_status',
            'created_at',  # 回傳欄位
        ]
        read_only_fields = ['id', 'start_time', 'rental_status', 'created_at']

    def validate_bike_id(self, value):
        try:
            bike = BikeInfo.objects.get(bike_id=value)
        except BikeInfo.DoesNotExist:
            raise serializers.ValidationError('Bike not found')

        # 檢查車輛即時狀態是否可租借
        try:
            realtime_status = bike.realtime_status
            if realtime_status.status != BikeRealtimeStatus.StatusOptions.IDLE:
                raise serializers.ValidationError('Bike is not available for rental')
        except BikeRealtimeStatus.DoesNotExist:
            raise serializers.ValidationError('Bike realtime status not found')

        return value

    def _find_member(self, member_email=None, member_phone=None):
        if not member_email and not member_phone:
            raise serializers.ValidationError(
                'Either member_email or member_phone is required'
            )

        # 建立查詢條件
        query = Q()
        if member_email:
            query |= Q(user__email=member_email)
        if member_phone:
            query |= Q(phone=member_phone)

        members = Member.objects.filter(query)
        member_count = members.count()

        if member_count == 0:
            raise serializers.ValidationError(ResponseMessage.MEMBER_NOT_FOUND)
        elif member_count > 1:
            raise serializers.ValidationError(ResponseMessage.MULTIPLE_MEMBERS_FOUND)

        return members.first()

    def validate(self, attrs):
        member_email = attrs.get('member_email')
        member_phone = attrs.get('member_phone')

        # 查找member
        member = self._find_member(member_email, member_phone)

        # 檢查是否已有活躍租借
        if hasattr(member, 'bike_realtime_status') and member.bike_realtime_status:
            raise serializers.ValidationError(
                'This member already has an active rental'
            )

        # 將找到的member存儲，供create方法使用
        attrs['_member'] = member
        return attrs

    def create(self, validated_data):
        bike_id = validated_data.pop('bike_id')
        # 移除不需要儲存到資料庫的欄位
        validated_data.pop('member_email', None)
        validated_data.pop('member_phone', None)
        member = validated_data.pop('_member')

        bike = BikeInfo.objects.get(bike_id=bike_id)

        rental = BikeRental.objects.create(
            member=member,
            bike=bike,
            start_time=timezone.now(),
            rental_status=BikeRental.RentalStatusOptions.ACTIVE,
            **validated_data
        )

        # 同步更新車輛即時狀態
        realtime_status = bike.realtime_status
        realtime_status.status = BikeRealtimeStatus.StatusOptions.RENTED
        realtime_status.current_member = member
        realtime_status.save()

        return rental


class BikeRentalStaffUpdateSerializer(serializers.ModelSerializer):
    action = serializers.ChoiceField(
        choices=RentalActionOption.choices, write_only=True
    )
    bike = BikeInfoSimpleSerializer(read_only=True)
    member = MemberSimpleSerializer(read_only=True)
    duration_minutes = serializers.ReadOnlyField(source='get_duration_minutes')

    class Meta:
        model = BikeRental
        fields = [
            'action',  # write_only 欄位
            'id',
            'bike',
            'member',
            'start_time',
            'end_time',
            'rental_status',
            'return_location',
            'total_fee',
            'memo',
            'duration_minutes',
            'updated_at',  # 回傳欄位
        ]

    def validate(self, attrs):
        action = attrs.get('action')

        if action == RentalActionOption.RETURN:
            if self.instance.rental_status not in [
                BikeRental.RentalStatusOptions.ACTIVE,
                BikeRental.RentalStatusOptions.RESERVED,
            ]:
                raise serializers.ValidationError('This rental cannot be returned')

        return attrs

    def update(self, instance, validated_data):
        action = validated_data.pop('action')

        if action == RentalActionOption.RETURN:
            instance.end_time = timezone.now()
            instance.rental_status = BikeRental.RentalStatusOptions.COMPLETED

            # 同步更新車輛即時狀態
            realtime_status = instance.bike.realtime_status
            realtime_status.status = BikeRealtimeStatus.StatusOptions.IDLE
            realtime_status.current_member = None
            realtime_status.save()

        # 更新其他欄位
        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save()
        return instance
