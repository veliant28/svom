from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers, status
from rest_framework.response import Response

from apps.backoffice.api.views._base import BackofficeAPIView
from apps.backoffice.services import ImportActionsService
from apps.supplier_imports.services.integrations.exceptions import SupplierCooldownError, SupplierIntegrationError


class RunImportSourceActionSerializer(serializers.Serializer):
    source_code = serializers.SlugField()
    dry_run = serializers.BooleanField(default=False)
    dispatch_async = serializers.BooleanField(default=False)
    reprice = serializers.BooleanField(required=False)
    reindex = serializers.BooleanField(required=False)
    file_paths = serializers.ListField(child=serializers.CharField(), required=False)


class ImportAllActionSerializer(serializers.Serializer):
    dry_run = serializers.BooleanField(default=False)
    dispatch_async = serializers.BooleanField(default=False)
    reprice = serializers.BooleanField(required=False)
    reindex = serializers.BooleanField(required=False)


class RepriceAfterImportActionSerializer(serializers.Serializer):
    run_id = serializers.UUIDField()
    dispatch_async = serializers.BooleanField(default=False)


class RunImportSourceActionAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = RunImportSourceActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        try:
            result = ImportActionsService().run_source(
                source_code=data["source_code"],
                dry_run=data.get("dry_run", False),
                dispatch_async=data.get("dispatch_async", False),
                reprice=data.get("reprice"),
                reindex=data.get("reindex"),
                file_paths=data.get("file_paths"),
                trigger="backoffice:run_source",
            )
        except ObjectDoesNotExist:
            return Response({"detail": "Import source not found."}, status=status.HTTP_404_NOT_FOUND)
        except SupplierCooldownError as exc:
            return Response(
                {
                    "detail": f"Слишком рано. Следующий запрос к UTR можно выполнить через {exc.retry_after_seconds} сек.",
                    "retry_after_seconds": exc.retry_after_seconds,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except SupplierIntegrationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"mode": result.mode, **result.payload}, status=status.HTTP_200_OK)


class ImportAllActionAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = ImportAllActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        result = ImportActionsService().run_all(
            dry_run=data.get("dry_run", False),
            dispatch_async=data.get("dispatch_async", False),
            reprice=data.get("reprice"),
            reindex=data.get("reindex"),
            trigger="backoffice:run_all",
        )

        return Response({"mode": result.mode, **result.payload}, status=status.HTTP_200_OK)


class RepriceAfterImportActionAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = RepriceAfterImportActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        try:
            result = ImportActionsService().reprice_after_import(
                run_id=str(data["run_id"]),
                dispatch_async=data.get("dispatch_async", False),
                trigger="backoffice:reprice_after_import",
            )
        except ObjectDoesNotExist:
            return Response({"detail": "Import run not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response({"mode": result.mode, **result.payload}, status=status.HTTP_200_OK)
