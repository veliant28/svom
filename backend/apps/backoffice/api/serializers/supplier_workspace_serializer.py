from rest_framework import serializers


class SupplierWorkspaceListItemSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    supplier_name = serializers.CharField()
    is_enabled = serializers.BooleanField()
    connection_status = serializers.CharField()
    last_successful_import_at = serializers.DateTimeField(allow_null=True)
    last_failed_import_at = serializers.DateTimeField(allow_null=True)
    can_run_now = serializers.BooleanField()
    cooldown_wait_seconds = serializers.IntegerField()


class SupplierWorkspaceConnectionSerializer(serializers.Serializer):
    login = serializers.CharField(allow_blank=True)
    has_password = serializers.BooleanField()
    access_token_masked = serializers.CharField(allow_blank=True)
    refresh_token_masked = serializers.CharField(allow_blank=True)
    access_token_expires_at = serializers.DateTimeField(allow_null=True)
    refresh_token_expires_at = serializers.DateTimeField(allow_null=True)
    token_obtained_at = serializers.DateTimeField(allow_null=True)
    last_token_refresh_at = serializers.DateTimeField(allow_null=True)
    last_token_error_at = serializers.DateTimeField(allow_null=True)
    last_token_error_message = serializers.CharField(allow_blank=True)
    credentials_updated_at = serializers.DateTimeField(allow_null=True)
    status = serializers.CharField()
    last_connection_check_at = serializers.DateTimeField(allow_null=True)
    last_connection_status = serializers.CharField(allow_blank=True)


class SupplierWorkspaceImportSerializer(serializers.Serializer):
    last_run_status = serializers.CharField(allow_blank=True)
    last_run_at = serializers.DateTimeField(allow_null=True)
    last_successful_import_at = serializers.DateTimeField(allow_null=True)
    last_failed_import_at = serializers.DateTimeField(allow_null=True)
    last_import_error_message = serializers.CharField(allow_blank=True)
    last_run_summary = serializers.JSONField()
    last_run_processed_rows = serializers.IntegerField()
    last_run_errors_count = serializers.IntegerField()


class SupplierWorkspaceCooldownSerializer(serializers.Serializer):
    last_request_at = serializers.DateTimeField(allow_null=True)
    next_allowed_request_at = serializers.DateTimeField(allow_null=True)
    can_run = serializers.BooleanField()
    wait_seconds = serializers.IntegerField()
    cooldown_seconds = serializers.IntegerField()
    status_label = serializers.CharField()


class SupplierWorkspaceUtrSerializer(serializers.Serializer):
    available = serializers.BooleanField()
    last_brands_import_at = serializers.DateTimeField(allow_null=True)
    last_brands_import_count = serializers.IntegerField()
    last_brands_import_error_at = serializers.DateTimeField(allow_null=True)
    last_brands_import_error_message = serializers.CharField(allow_blank=True)


class SupplierWorkspaceSupplierSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    supplier_name = serializers.CharField()
    is_enabled = serializers.BooleanField()


class SupplierWorkspaceSerializer(serializers.Serializer):
    supplier = SupplierWorkspaceSupplierSerializer()
    connection = SupplierWorkspaceConnectionSerializer()
    import_data = SupplierWorkspaceImportSerializer(source="import")
    cooldown = SupplierWorkspaceCooldownSerializer()
    utr = SupplierWorkspaceUtrSerializer()
