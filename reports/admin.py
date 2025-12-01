from django.contrib import admin

# Register your models here.
from .models import Build, TestRun, TestCaseRun

admin.site.register(Build)
admin.site.register(TestRun)
admin.site.register(TestCaseRun)