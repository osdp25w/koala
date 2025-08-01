from django.db import connection
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


@csrf_exempt
@require_http_methods(['GET'])
def health_check(request):
    return JsonResponse({'status': 'healthy'}, status=200)


@csrf_exempt
@require_http_methods(['GET'])
def readiness_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        return JsonResponse({'status': 'ready'}, status=200)
    except:
        return JsonResponse({'status': 'not_ready'}, status=503)
