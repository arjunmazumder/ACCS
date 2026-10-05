from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.models import Group, Permission
from .models import User
from lookup.serializers import LookupSerializer
from lookup.models import Lookup

def get_user_permissions(user):
    if not user or not user.is_authenticated:
        return []
    if user.is_superuser:
        return ["all"]
    direct_perms = user.user_permissions.values_list('codename', flat=True)
    group_perms = Permission.objects.filter(group__user=user).values_list('codename', flat=True)
    return sorted(list(set(list(direct_perms) + list(group_perms))))

class UserSerializer(serializers.ModelSerializer):
    role = LookupSerializer(read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Lookup.objects.all(),
        source='role',
        write_only=True,
        required=False,
        allow_null=True
    )
    groups = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name'
    )
    group_ids = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(),
        many=True,
        required=False,
        write_only=True,
        source='groups'
    )
    special_permission = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    permission_ids = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.all(),
        many=True,
        required=False,
        write_only=True,
        source='user_permissions'
    )
    
    class Meta:
        model = User
        fields = (
            'id', 'phone_number', 'full_name', 'date_of_birth', 
            'role', 'role_id', 'is_approved', 'is_phone_verified', 
            'is_active', 'is_staff', 'is_superuser', 
            'groups', 'group_ids', 'special_permission', 'permissions', 'permission_ids', 
            'created_at'
        )
        read_only_fields = ('id', 'created_at', 'is_superuser')

    def get_special_permission(self, obj):
        if not obj or not obj.is_authenticated:
            return []
        if obj.is_superuser:
            return ["all"]
        return sorted(list(obj.user_permissions.values_list('codename', flat=True)))

    def get_permissions(self, obj):
        return get_user_permissions(obj)

    def update(self, instance, validated_data):
        groups = validated_data.pop('groups', None)
        user_permissions = validated_data.pop('user_permissions', None)
        instance = super().update(instance, validated_data)
        if groups is not None:
            instance.groups.set(groups)
        if user_permissions is not None:
            instance.user_permissions.set(user_permissions)
        return instance
class RegisterSerializer(serializers.ModelSerializer):
    role = serializers.PrimaryKeyRelatedField(
        queryset=Lookup.objects.filter(is_active=True),
        required=False,
        allow_null=True
    )
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    
    # KYC Fields (Optional for BUYER, Required for VENDOR/others)
    profile_img = serializers.ImageField(required=False)
    nid_number = serializers.CharField(required=False, max_length=50)
    nid_front_image = serializers.ImageField(required=False)
    nid_back_image = serializers.ImageField(required=False)
    birth_certificate_image = serializers.ImageField(required=False)

    class Meta:
        model = User
        fields = ('phone_number', 'full_name', 'date_of_birth', 'role', 'password', 'confirm_password', 'profile_img', 'nid_number', 'nid_front_image', 'nid_back_image', 'birth_certificate_image')

    def validate(self, data):
        if data.get('password') != data.get('confirm_password'):
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
            
        role = data.get('role')
        # Default role is VENDOR; KYC/NID is required unless explicitly BUYER
        if not role or role.value.upper() != 'BUYER':
            errors = {}
            if not data.get('nid_number'):
                errors['nid_number'] = "NID number is required for Vendor registration."
            if not data.get('nid_front_image'):
                errors['nid_front_image'] = "NID front image is required for Vendor registration."
            if not data.get('nid_back_image'):
                errors['nid_back_image'] = "NID back image is required for Vendor registration."
            
            if errors:
                raise serializers.ValidationError(errors)
                
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')
        
        # Extract KYC data
        kyc_data = {
            'profile_img': validated_data.pop('profile_img', None),
            'nid_number': validated_data.pop('nid_number', None),
            'nid_front_image': validated_data.pop('nid_front_image', None),
            'nid_back_image': validated_data.pop('nid_back_image', None),
            'birth_certificate_image': validated_data.pop('birth_certificate_image', None),
        }
        
        # Default role to VENDOR if not provided
        role = validated_data.get('role')
        if not role:
            vendor_role = Lookup.objects.filter(name__iexact='ROLE', value__iexact='VENDOR').first()
            if not vendor_role:
                vendor_role, _ = Lookup.objects.get_or_create(name='ROLE', value='VENDOR', defaults={'is_active': True})
            role = vendor_role
            validated_data['role'] = vendor_role

        is_approved = False
        if role and role.value.upper() == 'BUYER':
            is_approved = True

        user = User.objects.create_user(
            password=password,
            is_approved=is_approved,
            **validated_data
        )
        
        # Automatically assign default Group (Role)
        group_name = role.value.lower() if role else 'vendor'
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)

        if role and role.value.upper() != 'BUYER':
            kyc_data = {k: v for k, v in kyc_data.items() if v is not None}
            KYCProfile.objects.create(user=user, **kyc_data)
            
        return user

class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(default='01711111111', initial='01711111111', help_text='Default: 01711111111')
    password = serializers.CharField(
        write_only=True, 
        default='12345678',
        initial='12345678',
        help_text='Default: 12345678',
        style={'input_type': 'password'}
    )

    def validate(self, data):
        phone_number = data.get('phone_number')
        password = data.get('password')

        if phone_number and password:
            user = authenticate(request=self.context.get('request'), phone_number=phone_number, password=password)
            if not user:
                raise serializers.ValidationError('Invalid phone number or password.')
                
            if not user.is_active:
                raise serializers.ValidationError('Your account has been suspended.')

            if not user.is_superuser and not user.is_staff:
                if not user.is_phone_verified:
                    raise serializers.ValidationError('Your phone number is not verified. Please verify OTP first.')
                
                if not user.is_approved:
                    raise serializers.ValidationError('Your account is pending admin approval.')
        else:
            raise serializers.ValidationError('Must include "phone_number" and "password".')
        
        data['user'] = user
        return data

class SendOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)

class VerifyOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    otp_code = serializers.CharField(max_length=6)

from .models import KYCProfile

class KYCProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = KYCProfile
        fields = ['id', 'user', 'profile_img', 'nid_number', 'nid_front_image', 'nid_back_image', 'birth_certificate_image', 'status', 'submitted_at', 'verified_at']
        read_only_fields = ['id', 'user', 'status', 'submitted_at', 'verified_at']

class ForgotPasswordSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)

class KYCProfileBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCProfile
        fields = ['id', 'profile_img', 'nid_number', 'nid_front_image', 'nid_back_image', 'birth_certificate_image', 'status', 'submitted_at', 'verified_at']
        read_only_fields = ['id', 'status', 'submitted_at', 'verified_at']

class UserWithProfileSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    kyc_profile = KYCProfileBasicSerializer(read_only=True)

    class Meta:
        model = User
        fields = ('user', 'kyc_profile')
        
    def get_user(self, obj):
        return UserSerializer(obj).data

class ResetPasswordSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    otp_code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=6)
    confirm_new_password = serializers.CharField(write_only=True, min_length=6)

    def validate(self, data):
        if data['new_password'] != data['confirm_new_password']:
            raise serializers.ValidationError("Passwords do not match.")
        return data

# --- BUYER AUTH SERIALIZERS ---
class BuyerRegisterSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    full_name = serializers.CharField(max_length=255)

class BuyerRegisterVerifySerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    otp_code = serializers.CharField(max_length=6)

from .models import ShippingAddress
class ShippingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = [
            'id', 'full_name', 'phone_number',
            'pathao_city_id', 'pathao_zone_id', 'pathao_area_id',
            'city_name', 'zone_name', 'area_name',
            'address', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'city_name', 'zone_name', 'area_name', 'created_at', 'updated_at']

    def create(self, validated_data):
        self._resolve_location_names(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        self._resolve_location_names(validated_data, instance=instance)
        return super().update(instance, validated_data)

    def _resolve_location_names(self, validated_data, instance=None):
        from orders.services.pathao import PathaoService
        pathao = PathaoService()
        
        city_id = validated_data.get('pathao_city_id') or (instance.pathao_city_id if instance else None)
        zone_id = validated_data.get('pathao_zone_id') or (instance.pathao_zone_id if instance else None)
        area_id = validated_data.get('pathao_area_id') or (instance.pathao_area_id if instance else None)

        if city_id:
            cities_resp = pathao.get_cities()
            if cities_resp and 'data' in cities_resp:
                for c in cities_resp['data'].get('data', []):
                    if c.get('city_id') == city_id:
                        validated_data['city_name'] = c.get('city_name')
                        break

        if zone_id:
            zones_resp = pathao.get_zones(city_id or 1)
            if zones_resp and 'data' in zones_resp:
                for z in zones_resp['data'].get('data', []):
                    if z.get('zone_id') == zone_id:
                        validated_data['zone_name'] = z.get('zone_name')
                        break

        if area_id:
            areas_resp = pathao.get_areas(zone_id or 101)
            if areas_resp and 'data' in areas_resp:
                for a in areas_resp['data'].get('data', []):
                    if a.get('area_id') == area_id:
                        validated_data['area_name'] = a.get('area_name')
                        break


# --- ADMIN / STAFF SERIALIZERS ---
class AdminLoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    password = serializers.CharField(
        write_only=True, 
        style={'input_type': 'password'}
    )

    def validate(self, data):
        phone_number = data.get('phone_number')
        password = data.get('password')

        if phone_number and password:
            user = authenticate(request=self.context.get('request'), phone_number=phone_number, password=password)
            if not user:
                raise serializers.ValidationError('Invalid phone number or password.')
                
            if not user.is_staff:
                raise serializers.ValidationError('You are not authorized to access the Admin Panel.')
            
            if not user.is_active:
                raise serializers.ValidationError('Your account has been suspended.')
        else:
            raise serializers.ValidationError('Must include "phone_number" and "password".')
        
        data['user'] = user
        return data

class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ('id', 'name', 'codename')

class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.all(),
        many=True,
        required=False
    )
    permission_details = PermissionSerializer(source='permissions', many=True, read_only=True)

    class Meta:
        model = Group
        fields = ('id', 'name', 'permissions', 'permission_details')

class StaffSerializer(serializers.ModelSerializer):
    groups = RoleSerializer(many=True, read_only=True)
    user_permissions = PermissionSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ('id', 'phone_number', 'full_name', 'is_staff', 'is_superuser', 'is_active', 'groups', 'user_permissions', 'created_at')

class StaffCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'}, min_length=6)
    group_ids = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(),
        many=True,
        required=False,
        write_only=True,
        source='groups'
    )
    permission_ids = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.all(),
        many=True,
        required=False,
        write_only=True,
        source='user_permissions'
    )

    class Meta:
        model = User
        fields = ('phone_number', 'full_name', 'password', 'group_ids', 'permission_ids')

    def create(self, validated_data):
        groups = validated_data.pop('groups', [])
        user_permissions = validated_data.pop('user_permissions', [])
        password = validated_data.pop('password')
        
        # Enforce staff rules
        validated_data['is_staff'] = True
        validated_data['is_approved'] = True
        validated_data['is_phone_verified'] = True
        
        user = User.objects.create_user(password=password, **validated_data)
        
        if groups:
            user.groups.set(groups)
        if user_permissions:
            user.user_permissions.set(user_permissions)
            
        return user

class StaffUpdateSerializer(serializers.ModelSerializer):
    group_ids = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(),
        many=True,
        required=False,
        write_only=True,
        source='groups'
    )
    permission_ids = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.all(),
        many=True,
        required=False,
        write_only=True,
        source='user_permissions'
    )

    class Meta:
        model = User
        fields = ('full_name', 'is_active', 'group_ids', 'permission_ids')

    def update(self, instance, validated_data):
        groups = validated_data.pop('groups', None)
        user_permissions = validated_data.pop('user_permissions', None)
        instance = super().update(instance, validated_data)
        
        if groups is not None:
            instance.groups.set(groups)
        if user_permissions is not None:
            instance.user_permissions.set(user_permissions)
            
        return instance


class MeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('full_name', 'date_of_birth')


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=6)
    confirm_new_password = serializers.CharField(write_only=True, min_length=6)

    def validate(self, data):
        if data['new_password'] != data['confirm_new_password']:
            raise serializers.ValidationError({"confirm_new_password": "Passwords do not match."})
        return data
