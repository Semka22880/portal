# reports/management/commands/auto_import_allure.py
import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from reports.models import Build, TestRun, TestCaseRun

BASE_URL = "http://10.177.140.34:8080"
API_REPORT_URL = f"{BASE_URL}/api/report"      # Этот точно работает у тебя


class Command(BaseCommand):
    help = "Импорт всех билдов через API — с правильными датами и архитектурами"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--limit', type=int, default=0)
        parser.add_argument('--use-reports', action='store_true', help='Использовать /api/report (рекомендуется)')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']
        api_url = API_REPORT_URL if options['use_reports'] else f"{BASE_URL}/api/results"

        self.stdout.write(f"Получаем список билдов с: {api_url}")
        try:
            r = requests.get(api_url, timeout=30)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"API недоступен: {e}"))
            return

        # Поддержка разных форматов ответа
        if isinstance(data, list):
            reports = data
        elif isinstance(data, dict) and 'items' in data:
            reports = data['items']
        elif isinstance(data, dict) and 'data' in data:
            reports = data['data']
        else:
            self.stdout.write(self.style.ERROR("Неизвестный формат ответа API"))
            return

        self.stdout.write(self.style.SUCCESS(f"Найдено {len(reports)} билдов"))

        imported = skipped = failed = 0

        for idx, report in enumerate(reports[:limit or None]):
            uuid = report.get('uuid') or report.get('uid') or report.get('id')
            build_number = report.get('name') or report.get('title') or report.get('path') or f"unknown-{idx}"

            if not uuid:
                self.stdout.write(self.style.WARNING(f"Пропуск: нет UUID"))
                continue


                       # УНИВЕРСАЛЬНЫЙ ПАРСЕР ДАТЫ — РАБОТАЕТ СО ВСЕМИ ВАРИАНТАМИ ALLURE
            timestamp = (
                report.get('created') or
                report.get('timestamp') or
                report.get('startTime') or
                report.get('start') or
                report.get('date')
            )

            build_date = datetime.now().date()  # fallback

            if not timestamp:
                pass
            elif isinstance(timestamp, (int, float)):
                # миллисекунды с 1970
                build_date = datetime.fromtimestamp(timestamp / 1000).date()
            elif isinstance(timestamp, str):
                timestamp = timestamp.strip().replace('Z', '+00:00')
                # Список всех форматов, которые реально встречаются в Allure
                formats = [
                    "%Y-%m-%dT%H:%M:%S.%f%z",   # 2025-04-05T12:34:56.789+00:00
                    "%Y-%m-%dT%H:%M:%S%z",      # 2025-04-05T12:34:56+00:00
                    "%Y-%m-%d %H:%M:%S",        # 2025-04-05 12:34:56
                    "%d/%m/%Y %H:%M:%S",        # 05/04/2025 12:34:56
                    "%Y-%m-%d",                # просто дата
                ]
                for fmt in formats:
                    try:
                        build_date = datetime.strptime(timestamp, fmt)
                        if build_date.year < 1900:  # защита от мусора
                            continue
                        build_date = build_date.date()
                        break
                    except:
                        continue




            #Архитектура
            name = build_number.upper()
            if name.startswith('SMK-MOB-'):
                architecture = 'Mobile'
                build_type = 'Mobile'
            elif name.startswith('SMK-RUN18-'):
                architecture = 'Run18'
                build_type = 'Run18'
            elif name.startswith('SMK-RUN17-'):
                architecture = 'Run17'
                build_type = 'Run17'
            elif name.startswith('SMK-INIT18-'):
                architecture = 'Init18'
                build_type = 'Init18'
            elif name.startswith('SMK-BNCH-'):
                architecture = 'Benchmark'
                build_type = 'Benchmark'
            else:
                architecture = 'Other'
                build_type = 'Other'

            if Build.objects.filter(build_number=build_number).exists():
                skipped += 1
                continue

            self.stdout.write(f"[{idx+1}] Импорт: {build_number} → {build_type} ({build_date})")

            if dry_run:
                continue

            # Скачиваем suites.csv для статистики
            csv_url = f"{BASE_URL}/allure/reports/{uuid}/data/suites.csv"
            try:
                csv_r = requests.get(csv_url, timeout=40)
                csv_r.raise_for_status()
                csv_content = csv_r.text
            except:
                self.stdout.write(self.style.WARNING("  CSV недоступен — пропускаем статистику"))
                csv_content = ""

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
                    total_tests=0, passed_tests=0, failed_tests=0, skipped_tests=0
                )

                if csv_content:
                    from io import StringIO
                    import csv
                    reader = csv.DictReader(StringIO(csv_content))
                    passed = failed_t = skipped_t = 0
                    for row in reader:
                        status = row.get('Status', '').lower()
                        name = row.get('Test Method') or row.get('Name') or 'unknown'
                        TestCaseRun.objects.create(
                            test_run=test_run,
                            test_name=name.strip(),
                            status=status,
                            execution_date=build_date
                        )
                        if status == 'passed': passed += 1
                        elif status == 'failed': failed_t += 1
                        elif status == 'skipped': skipped_t += 1

                    test_run.total_tests = passed + failed_t + skipped_t
                    test_run.passed_tests = passed
                    test_run.failed_tests = failed_t
                    test_run.skipped_tests = skipped_t
                    test_run.save()

                imported += 1
                self.stdout.write(self.style.SUCCESS(f"  Успешно: {build_number} | {architecture} | {passed}p/{failed_t}f"))

        self.stdout.write(self.style.SUCCESS(f"\nГОТОВО! Импортировано: {imported} | Пропущено: {skipped} | Ошибок: {failed}"))
