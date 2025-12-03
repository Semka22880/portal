# reports/views.py
from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Prefetch
from .models import Build, TestRun, TestCaseRun


def build_list(request):
    """Список всех билдов с фильтрами по типу"""
    selected_type = request.GET.get('type', 'all')
    
    builds = Build.objects.all().order_by('-date')
    
    if selected_type != 'all':
        builds = builds.filter(build_type=selected_type)
    
    type_counts = Build.objects.values('build_type').annotate(count=Count('id'))
    type_counts_dict = {item['build_type']: item['count'] for item in type_counts}
    
    context = {
        'builds': builds,
        'selected_type': selected_type,
        'type_counts': type_counts_dict,
        'total_builds': Build.objects.count(),
    }
    return render(request, 'reports/build_list.html', context)


def build_detail(request, build_id):
    """Детальная страница билда — со всеми тестами"""
    build = get_object_or_404(Build, id=build_id)
    
    # Подгружаем все тесты сразу — без N+1 запросов
    test_runs = build.test_runs.all().prefetch_related(
        Prefetch('cases', queryset=TestCaseRun.objects.all())
    )
    
    return render(request, 'reports/build_detail.html', {
        'build': build,
        'test_runs': test_runs,
    })


def test_history(request, test_name, architecture):
    """История конкретного теста — только по выбранной архитектуре"""
    runs = TestCaseRun.objects.filter(
        test_name=test_name,
        architecture=architecture
    ).select_related('test_run__build').order_by('-execution_date')

    context = {
        'test_name': test_name,
        'architecture': architecture,
        'runs': runs,
        'total_runs': runs.count(),
        'passed_count': runs.filter(status='passed').count(),
        'failed_count': runs.filter(status='failed').count(),
        'skipped_count': runs.filter(status='skipped').count(),
    }
    return render(request, 'reports/test_history.html', context)
