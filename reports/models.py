from django.db import models

class Build(models.Model):
    build_number = models.CharField(max_length=50, unique=True)  # Номер билда, e.g., 'SMK-MOB-T17-593'
    date = models.DateField()  # Дата билда
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Build {self.build_number} ({self.date})"

class TestRun(models.Model):
    build = models.ForeignKey(Build, on_delete=models.CASCADE, related_name='test_runs')
    architecture = models.CharField(max_length=100)  # Архитектура, e.g., 'Astra 1.8'
    os_version = models.CharField(max_length=50)  # Версия ОС
    status = models.CharField(max_length=20, choices=[('passed', 'Passed'), ('failed', 'Failed'), ('skipped', 'Skipped')])  # Общий статус
    total_tests = models.IntegerField(default=0)
    passed_tests = models.IntegerField(default=0)
    failed_tests = models.IntegerField(default=0)
    skipped_tests = models.IntegerField(default=0)
    run_date = models.DateField()  # Дата прогона
    allure_report_url = models.URLField(blank=True, null=True)  # Ссылка на Allure-отчёт

    def __str__(self):
        return f"TestRun for {self.build} on {self.architecture}"

class TestCaseRun(models.Model):
    test_run = models.ForeignKey(TestRun, on_delete=models.CASCADE, related_name='test_cases')
    test_name = models.CharField(max_length=200)  # Имя теста, e.g., 'astra-ilev1-control'
    status = models.CharField(max_length=20, choices=[('passed', 'Passed'), ('failed', 'Failed'), ('skipped', 'Skipped')])
    execution_date = models.DateField()  # Дата выполнения этого теста

    def __str__(self):
        return f"{self.test_name} in {self.test_run}"