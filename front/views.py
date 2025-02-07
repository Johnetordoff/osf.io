from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import View
from rest_framework import status
from django.http import JsonResponse
from framework.auth.views import forgot_password_post

@method_decorator(csrf_exempt, name='dispatch')  # ✅ Disable CSRF for this view
class ResetPasswordView(View):
    def post(self, request, *args, **kwargs):
        forgot_password_post()
        return JsonResponse({'message': 'Password reset link sent successfully!'}, status=status.HTTP_200_OK)
