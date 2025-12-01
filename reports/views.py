from django.shortcuts import render

# Create your views here.
from .models import Build

def build_list(request):
    builds = Build.objects.all().order_by('-date')  # Сортировка по дате descending
    return render(request, 'reports/build_list.html', {'builds': builds})


from django.shortcuts import render, get_object_or_404
from .models import Build

def build_detail(request, build_id):
    build = get_object_or_404(Build, id=build_id)
    test_runs = build.test_runs.all()
    return render(request, 'reports/build_detail.html', {'build': build, 'test_runs': test_runs})


from django.db.models import Max
from .models import TestCaseRun

def test_history(request, test_name):
    runs = TestCaseRun.objects.filter(test_name=test_name) \
                              .select_related('test_run__build') \
                              .order_by('-execution_date')
    
    last_success = runs.filter(status='passed').first()
    last_success_date = last_success.execution_date if last_success else None

    return render(request, 'reports/test_history.html', {
        'test_name': test_name,
        'runs': runs,
        'last_success': last_success_date
    })