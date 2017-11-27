from pathlib import PurePath
from tempfile import mkdtemp

from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from apps.core.factories import PIXELER_PASSWORD, PixelerFactory
from apps.submission.io.xlsx import (
    sha256_checksum, generate_template, get_template_version
)
from apps.submission.models import SubmissionProcess


class StartViewTestCase(TestCase):

    url = reverse('submission:start')
    template = 'submission/submission/start.html'

    def setUp(self):

        self.user = PixelerFactory(
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        self.client.login(
            username=self.user.username,
            password=PIXELER_PASSWORD,
        )

    def test_get_start_view(self):

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, self.template)

    def test_create_new_process(self):

        label = 'Candida datasest 0001'
        response = self.client.post(
            self.url,
            data={
                'label': label,
                '_viewflow_activation-started': '2000-01-01',
            }
        )

        self.assertEqual(response.status_code, 302)

        response = self.client.post(
            self.url,
            data={
                'label': label,
                '_viewflow_activation-started': '2000-01-01',
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        expected_template = 'submission/submission/process_detail.html'
        self.assertTemplateUsed(response, expected_template)


class DownloadXLSXTemplateViewTestCase(TestCase):

    template = 'submission/download_xlsx_template.html'

    def setUp(self):

        self.user = PixelerFactory(
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        self.client.login(
            username=self.user.username,
            password=PIXELER_PASSWORD,
        )
        self.client.post(
            reverse('submission:start'),
            data={
                'label': 'Candida datasest 0001',
                '_viewflow_activation-started': '2000-01-01',
            },
            follow=True,
        )

        self.process = SubmissionProcess.objects.get()
        self.task = self.process.task_set.first()
        params = {
            'process_pk': self.process.pk,
            'task_pk': self.task.pk,
        }
        self.url = reverse('submission:download', kwargs=params)

    def test_get(self):

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, self.template)

    def test_get_context_data(self):

        response = self.client.get(self.url)
        self.assertListEqual(
            list(response.context.get('task_list')),
            list(self.process.task_set.all().order_by('created'))
        )

    def test_post(self):

        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)

        template_path = PurePath(mkdtemp(), 'meta.xlsx')
        _, expected_version = generate_template(template_path)

        self.assertEqual(
            response.get('Content-Disposition'),
            'attachment; filename="{}"'.format(
                '{}-{}.xlsx'.format(
                    template_path.stem,
                    expected_version[:8]
                )
            )
        )

        expected_content_type = (
            'application/vnd'
            '.openxmlformats-officedocument'
            '.spreadsheetml'
            '.sheet'
        )
        self.assertEqual(
            response.get('Content-Type'),
            expected_content_type
        )

    def test_generated_file(self):

        response = self.client.post(self.url)
        process = SubmissionProcess.objects.get()

        # Write generated file
        template_file_name = 'meta.xlsx'
        template_path = PurePath(mkdtemp(), template_file_name)
        with open(template_path, 'wb') as template_file:
            template_file.write(response.content)

        expected_checksum = sha256_checksum(template_path)
        self.assertEqual(
            process.template_checksum,
            expected_checksum
        )

        expected_version = get_template_version(template_path)
        self.assertEqual(
            process.template_version,
            expected_version
        )

        # Try to open it as an excel workbook and smoke test it
        wb = load_workbook(template_path)
        ws = wb.active
        self.assertEqual(ws.title, 'Import information for Pixel')