# reports/management/commands/auto_import_allure.py
# УНИВЕРСАЛЬНЫЙ ИМПОРТ ЧЕРЕЗ API — ИСПРАВЛЕННАЯ ВЕРСИЯ

import csv
import io
import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from reports.models import Build, TestRun, TestCaseRun


# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
# ТУТ БУДЕТ ТВОЙ НАСТОЯЩИЙ API — ПОКА ОСТАВЬ КАК ЕСТЬ
API_URL = "http://10.177.140.34:8080/allure/reports/api/reports"
# ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
# Как получишь настоящий URL — заменишь эту строку и всё заработает


class Command(BaseCommand):
    help = "Универсальный импорт всех билдов через API Allure (готов к реальному URL)"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Только показать')
        parser.add_argument('--limit', type=int, default=0, help='Ограничить количество')
        parser.add_argument('--api-url', type=str, help='Переопределить URL из команды')

    def handle(self, *args, **options):
        api_url = options['api_url'] or API_URL
        dry_run = options['dry_run']
        limit = options['limit']

        self.stdout.write(f"Пытаемся получить список билдов с:\n    {api_url}")

        try:
            r = requests.get(api_url, timeout=20)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"API недоступен: {e}"))
            self.stdout.write(self.style.ERROR("Пока API нет — команда просто ждёт настоящий URL"))
            return

        # Поддержка разных форматов ответа
        if isinstance(data, dict) and 'items' in data:
            reports = data['items']
        elif isinstance(data, dict) and 'data' in data:
            reports = data['data']
        elif isinstance(data, list):
            reports = data
        else:
            self.stdout.write(self.style.ERROR("Неизвестный формат JSON"))
            return

        self.stdout.write(self.style.SUCCESS(f"УСПЕШНО! Получено {len(reports)} билдов"))

        imported = skipped = failed = 0

        for idx, report in enumerate(reports[:limit or None]):
            # ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
            # УКАЖИ ПРАВИЛЬНЫЕ ПОЛЯ ИЗ ТВОЕГО API (примеры ниже)
            uuid = report.get('uuid') or report.get('id') or report.get('reportId')
            build_number = report.get('name') or report.get('reportName') or report.get('title')
            timestamp = report.get('created') or report.get('timestamp') or report.get('startTime')
            # ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑

            if not uuid or not build_number:
                self.stdout.write(self.style.WARNING(f"Пропуск строки {idx+1} — нет uuid или имени"))
                continue

            # Дата
            if isinstance(timestamp, (int, float)):
                build_date = datetime.fromtimestamp(timestamp / 1000).date()
            else:
                build_date = datetime.now().date()

            if Build.objects.filter(build_number=build_number).exists():
                skipped += 1
                continue

            self.stdout.write(f"[{idx+1}/{len(reports)}] {build_number}")

            if dry_run:
                continue

            csv_url = f"http://10.177.140.34:8080/allure/reports/{uuid}/data/suites.csv"
            try:
                csv_r = requests.get(csv_url, timeout=40)
                csv_r.raise_for_status()
                csv_content = csv_r.text
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  CSV не найден: {e}"))
                failed += 1
                continue

            architecture = self.extract_architecture(csv_content)

            with transaction.atomic():
                build, _ = Build.objects.get_or_create(build_number=build_number, defaults={'date': build_date})
                test_run = TestRun.objects.create(
                    build=build, architecture=architecture, run_date=build_date,
                    allure_report_url=f"http://10.177.140.34:8080/allure/reports/{uuid}/",
                    total_tests=0, passed_tests=0, failed_tests=0, skipped_tests=0
                )

                passed = failed_t = skipped_t = 0
                for row in csv.DictReader(io.StringIO(csv_content)):
                    status = row.get('Status', '').lower()
                    name = row.get('Test Method') or row.get('Name', 'unknown')
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
                self.stdout.write(self.style.SUCCESS(f"  {build_number} → {architecture} | {passed}p/{failed_t}f/{skipped_t}s"))

        self.stdout.write(self.style.SUCCESS(f"\nГОТОВО! Импортировано: {imported} | Пропущено: {skipped} | Ошибок: {failed}"))

    # ИСПРАВЛЕНА ОШИБКА С КАВЫЧКОЙ
    def extract_architecture(self, csv_content: str) -> str:
        reader = csv.DictReader(io.StringIO(csv_content))
        for row in list(reader)[:10]:
            suite = row.get("Suite") or row.get("Parent Suite") or ""
            if "." in suite:
                return suite.split(".", 1)[0].strip()
        return "Unknown Architecture"