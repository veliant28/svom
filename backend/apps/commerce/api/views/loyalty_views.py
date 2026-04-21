from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.commerce.api.serializers import LoyaltyPromoCodeSerializer
from apps.commerce.selectors import list_user_loyalty_codes


class LoyaltyMyPromoCodesAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        promos = list_user_loyalty_codes(user=request.user)
        serializer = LoyaltyPromoCodeSerializer(promos, many=True)
        return Response(serializer.data)
