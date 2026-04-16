from rest_framework.pagination import PageNumberPagination


class SupplierRawOfferPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 500
    allowed_page_sizes = {15, 25, 50, 100, 500}

    def get_page_size(self, request):
        raw_value = request.query_params.get(self.page_size_query_param)
        if raw_value in (None, ""):
            return self.page_size

        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            return self.page_size

        if value in self.allowed_page_sizes:
            return value

        return self.page_size
