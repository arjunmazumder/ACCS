from rest_framework.permissions import BasePermission

class AdminBypassPermission(BasePermission):
    """
    A base permission class that automatically grants full access 
    to Admins and SuperAdmins, bypassing all other checks.
    """
    def is_admin(self, request):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.is_staff:
            return True
        if user.role and user.role.name == 'ROLE' and user.role.value == 'ADMIN':
            return True
        return False

    def has_permission(self, request, view):
        if self.is_admin(request):
            return True
        return self.has_custom_permission(request, view)

    def has_object_permission(self, request, view, obj):
        if self.is_admin(request):
            return True
        return self.has_custom_object_permission(request, view, obj)
        
    def has_custom_permission(self, request, view):
        return True
        
    def has_custom_object_permission(self, request, view, obj):
        return True

class IsAdminOrSuperAdmin(AdminBypassPermission):
    """
    Allows access only to superusers or users with the 'ADMIN' role.
    """
    def has_custom_permission(self, request, view):
        # Admin is handled by base class, so if it reaches here and it's not admin, return False.
        # But base class grants True for admins. So this class is effectively just checking base class logic.
        return False

class IsBuyer(AdminBypassPermission):
    """
    Allows access only to users with the 'BUYER' role.
    """
    def has_custom_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.role and 
            request.user.role.name == 'ROLE' and 
            request.user.role.value == 'BUYER'
        )

class IsRetailer(AdminBypassPermission):
    """
    Allows access only to users with the 'RETAILER' role.
    """
    def has_custom_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.role and 
            request.user.role.name == 'ROLE' and 
            request.user.role.value == 'RETAILER'
        )

class IsWholesaler(AdminBypassPermission):
    """
    Allows access only to users with the 'WHOLESALER' role.
    """
    def has_custom_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.role and 
            request.user.role.name == 'ROLE' and 
            request.user.role.value == 'WHOLESALER'
        )

class IsServiceProvider(AdminBypassPermission):
    """
    Allows access only to users with the 'SERVICE_PROVIDER' role.
    """
    def has_custom_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.role and 
            request.user.role.name == 'ROLE' and 
            request.user.role.value == 'SERVICE_PROVIDER'
        )

class IsAdminOrSuperAdminOrServiceProvider(AdminBypassPermission):
    """
    Allows access only to superusers, or users with the 'ADMIN' or 'SERVICE_PROVIDER' role.
    """
    def has_custom_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        if request.user.role and request.user.role.name == 'ROLE':
            return request.user.role.value in ['SERVICE_PROVIDER']
            
        return False

class IsAdminOrSuperAdminOrBuyer(AdminBypassPermission):
    """
    Allows access only to superusers, or users with the 'ADMIN' or 'BUYER' role.
    """
    def has_custom_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        if request.user.role and request.user.role.name == 'ROLE':
            return request.user.role.value in ['BUYER']
            
        return False

class IsVendor(AdminBypassPermission):
    """
    Allows access only to users with 'VENDOR', 'RETAILER', or 'WHOLESALER' role.
    """
    def has_custom_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.is_active and
            request.user.role and 
            request.user.role.name == 'ROLE' and 
            request.user.role.value.upper() in ['VENDOR', 'RETAILER', 'WHOLESALER']
        )

class IsVendorOrReadOnly(AdminBypassPermission):
    """
    Safe methods (GET, HEAD, OPTIONS) allowed for all.
    Write methods (POST, PUT, PATCH, DELETE) only allowed for VENDOR / RETAILER / WHOLESALER (or ADMIN).
    Object-level: Only the shop owner (or Admin) can modify/delete their own shop.
    """
    def has_custom_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.is_active and
            request.user.role and 
            request.user.role.name == 'ROLE' and 
            request.user.role.value.upper() in ['VENDOR', 'RETAILER', 'WHOLESALER']
        )

    def has_custom_object_permission(self, request, view, obj):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        owner = getattr(obj, 'user', None)
        return owner == request.user

class IsServiceProviderOrReadOnly(AdminBypassPermission):
    """
    Safe methods (GET, HEAD, OPTIONS) allowed for all.
    Write methods only allowed for SERVICE_PROVIDER (or ADMIN).
    Object-level: Only the business profile owner (or Admin) can modify/delete their profile.
    """
    def has_custom_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.is_active and
            request.user.role and 
            request.user.role.name == 'ROLE' and 
            request.user.role.value == 'SERVICE_PROVIDER'
        )

    def has_custom_object_permission(self, request, view, obj):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        owner = getattr(obj, 'provider', None) or getattr(obj, 'user', None)
        return owner == request.user

class HasRequiredPermission(AdminBypassPermission):
    """
    Checks if the authenticated user has the required permission codename.
    Admins / Superadmins / Staff bypass automatically.
    """
    required_permission = None

    def has_custom_permission(self, request, view):
        perm = getattr(view, 'required_permission', self.required_permission)
        if not perm:
            return True
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.has_perm(perm)
        )
