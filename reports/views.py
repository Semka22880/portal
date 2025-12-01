from django.shortcuts import render
from django.http import HttpResponse
from .allure_import import import_report
from .models import Report

def index(request):
    return render(request, "index.html")

def import_view(request, uuid):
    import_report(uuid)
    return HttpResponse("Импорт завершён.")


def index(request):
    reports = Report.objects.order_by("-created_at")
    return render(request, "index.html", {"reports": reports})
