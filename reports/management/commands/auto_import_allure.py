# reports/management/commands/auto_import_allure.py
# Рабочая версия: дата берётся из максимального Stop Time в suites.csv

import csv
import io
import requests
from datetime import datetime
from dateutil import parser as dateutil_parser

from django.core.management.base import BaseCommand
from django.db import transaction

from reports.models import Build, TestRun, TestCaseRun


BASE_URL = "http://10.177.140.34:8080"
API_REPORT_URL = f"{BASE_URL}/api/report"


class Command(BaseCommand):
    help = "Импорт Allure-отчётов: дата из max(Stop Time) в CSV"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--limit', type=int, default=0)

    def get_build_date_from_csv(self, csv_content):
            """Правильно парсит Tue Dec 02 04:59:10 MSK 2025 и любые другие форматы"""
            from dateutil import parser as dateutil_parser  # ← это спасение

            reader = csv.DictReader(io.StringIO(csv_content))
            dates = []

            for row in reader:
                stop = row.get('Stop Time') or row.get('Start Time')
                if not stop:
                    continue
                try:
                    # Самый надёжный способ — dateutil умеет парсить ВСЁ
                    dt = dateutil_parser.parse(stop, tzinfos={"MSK": 3 * 3600, "MST": 7 * 3600})
                    dates.append(dt)
                except:
                    continue

            if dates:
                return max(dates).date()
            return datetime.now().date()

    def get_type_and_arch(self, name):
        n = name.upper()
        if n.startswith('SMK-MOB-'):    return 'Mobile', 'Mobile'
        if n.startswith('SMK-RUN18-'):  return 'Run18', 'Run18'
        if n.startswith('SMK-RUN17-'):  return 'Run17', 'Run17'
        if n.startswith('SMK-INIT18-'): return 'Init18', 'Init18'
        if n.startswith('SMK-BNCH-'):   return 'Benchmark', 'Benchmark'
        return 'Other', 'Other'

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']

        self.stdout.write("Получаем список отчётов...")
        resp = requests.get(API_REPORT_URL, timeout=30)
        resp.raise_for_status()
        reports = resp.json() if isinstance(resp.json(), list) else resp.json().get('items', [])

        self.stdout.write(self.style.SUCCESS(f"Найдено {len(reports)} отчётов"))

        imported = skipped = 0

        for idx, rep in enumerate(reports[:limit or None]):
            uuid = rep.get('uuid')
            build_number = rep.get('path') or rep.get('name')

            if not uuid or not build_number:
                continue

            # Скачиваем CSV (он обязателен для даты и статистики)
            csv_url = f"{BASE_URL}/allure/reports/{uuid}/data/suites.csv"
            try:
                csv_resp = requests.get(csv_url, timeout=40)
                csv_resp.raise_for_status()
                csv_content = csv_resp.text
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"CSV недоступен для {build_number}: {e}"))
                continue

            # Дата прогона
            build_date = self.get_build_date_from_csv(csv_content)

            # Тип и архитектура по имени билда
            build_type, architecture = self.get_type_and_arch(build_number)

            if Build.objects.filter(build_number=build_number).exists():
                skipped += 1
                continue

            self.stdout.write(f"[{idx+1}] {build_number} → {build_type} ({build_date})")

            if dry_run:
                imported += 1
                continue

            with transaction.atomic():
                build = Build.objects.create(
                    build_number=build_number,
                    date=build_date,
                    build_type=build_type
                )

                test_run = TestRun.objects.create(
                    build=build,
                    architecture=architecture,
                    run_date=build_date,
                    allure_report_url=f"{BASE_URL}/allure/reports/{uuid}/",
                    total_tests=0,
                    passed_tests=0,
                    failed_tests=0,
                    skipped_tests=0,
                )

                # Заполняем статистику и TestCaseRun
                reader = csv.DictReader(io.StringIO(csv_content))
                passed = failed = skipped_cnt = 0

                for row in reader:
                    status = row.get('Status', '').lower()
                    name = (row.get('Test Method') or row.get('Name') or 'unknown').strip()

                    TestCaseRun.objects.create(
                        test_run=test_run,
                        test_name=name,
                        status=status,
                        execution_date=build_date,
                        architecture=architecture,          # ← важно для фильтрации истории
                    )

                    if status == 'passed':
                        passed += 1
                    elif status == 'failed':
                        failed += 1
                    elif status == 'skipped':
                        skipped_cnt += 1

                test_run.total_tests = passed + failed + skipped_cnt
                test_run.passed_tests = passed
                test_run.failed_tests = failed
                test_run.skipped_tests = skipped_cnt
                test_run.save()

                imported += 1
                self.stdout.write(self.style.SUCCESS(f"  Успешно: {passed}p / {failed}f / {skipped_cnt}s"))

        self.stdout.write(self.style.SUCCESS(f"\nГОТОВО! Импортировано: {imported} | Пропущено: {skipped}"))
