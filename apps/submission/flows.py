import logging

from pathlib import Path

import background

from django import db
from django.conf import settings
from django.utils.timezone import now
from viewflow import flow, signals as vf_signals
from viewflow.activation import Context, STATUS
from viewflow.base import this, Flow
from viewflow.flow.views import CreateProcessView
from viewflow.nodes.handler import HandlerActivation

from . import views
from .models import SubmissionProcess
from .io.archive import PixelArchive

logger = logging.getLogger(__name__)


class NotPropagatedExceptionHandlerActivation(HandlerActivation):

    def perform(self):

        with Context(propagate_exception=False):
            super().perform()


class AsyncActivationHandler(NotPropagatedExceptionHandlerActivation):

    def perform(self):

        with self.exception_guard():
            self.task.started = now()

            vf_signals.task_started.send(
                sender=self.flow_class,
                process=self.process,
                task=self.task
            )
            self.execute()

    def callback(self):

        with Context(propagate_exception=False):
            with self.exception_guard():
                logger.debug('Activation class callback started…')

                self.task.finished = now()
                self.set_status(STATUS.DONE)
                self.task.save()

                vf_signals.task_finished.send(
                    sender=self.flow_class,
                    process=self.process,
                    task=self.task
                )

                self.activate_next()


class AsyncHandler(flow.Handler):

    activation_class = AsyncActivationHandler


class SubmissionFlow(Flow):

    process_class = SubmissionProcess

    start = flow.Start(
        CreateProcessView,
        fields=['label']
    ).Permission(
        auto_create=True
    ).Next(
        this.download
    )

    download = flow.View(
        views.DownloadXLSXTemplateView,
    ).Assign(
        this.start.owner
    ).Next(
        this.check_download
    )

    check_download = flow.If(
        lambda activation: activation.process.downloaded
    ).Then(
        this.upload
    ).Else(
        this.download
    )

    upload = flow.View(
        views.UploadArchiveView,
    ).Assign(
        this.start.owner
    ).Next(
        this.check_upload
    )

    check_upload = flow.If(
        lambda activation: activation.process.uploaded
    ).Then(
        this.meta
    ).Else(
        this.upload
    )

    meta = flow.Handler(
        this.parse_meta,
        activation_class=NotPropagatedExceptionHandlerActivation,
    ).Next(
        this.check_meta
    )

    check_meta = flow.If(
        lambda activation: activation.process.meta is not None
    ).Then(
        this.validation
    ).Else(
        this.upload
    )

    validation = flow.View(
        views.ArchiveValidationView,
    ).Assign(
        this.start.owner
    ).Next(
        this.check_validation
    )

    check_validation = flow.If(
        lambda activation: activation.process.validated
    ).Then(
        this.tags
    ).Else(
        this.validation
    )

    tags = flow.View(
        views.TagsView,
    ).Assign(
        this.start.owner
    ).Next(
        this.import_archive
    )

    import_archive = AsyncHandler(
        this.perform_archive_importation,
    ).Next(
        this.check_import
    )

    check_import = flow.If(
        lambda activation: activation.process.imported
    ).Then(
        this.end
    ).Else(
        this.validation
    )

    end = flow.End()

    def get_archive_path(self, activation):
        return Path(
            settings.MEDIA_ROOT
        ) / Path(
            activation.process.archive.name
        )

    def parse_meta(self, activation):

        archive_path = self.get_archive_path(activation)
        archive = PixelArchive(archive_path)
        archive.parse(serialized=True)
        activation.process.meta = archive.meta
        activation.process.save()

    def perform_archive_importation(self, activation):

        archive_path = self.get_archive_path(activation)
        process = activation.process
        pixeler = process.created_by
        task = process.get_task(self.import_archive)

        @background.task
        def async_import_archive():
            logger.debug("Async import started…")

            archive = PixelArchive(archive_path)
            logger.debug("Archive instanciated")

            logger.debug("Saving archive…")
            return archive.save(pixeler=pixeler, submission=process)

        @background.callback
        def importation_callback(future):
            """
            We need to force databases connection closing since the background
            process (in a separated thread) creates a new connection that would
            never be closed otherwise.
            """
            logger.debug("Background importation callback started…")

            e = future.exception()
            logger.debug("Future exception: {} ({})".format(e, type(e)))

            if e is not None:
                task.status = STATUS.ERROR
                task.comments = str(e)
                task.finished = now()
                task.save()

                # Re-raise the exception for lazy logging
                try:
                    raise e
                except Exception:
                    logger.exception(
                        "Importation failed! archive: {} (pixeler: {})".format(
                            archive_path,
                            pixeler
                        )
                    )
                    logger.debug(
                        "Closing open database connections "
                        "(background callback exception)"
                    )
                    db.connections.close_all()
                    raise

            process.imported = True
            process.save()
            logger.debug("Submission process updated (imported: True)")

            logger.debug("Proceeding with activation callback")
            activation.callback()

            logger.debug(
                "Closing open database connections (background callback)"
            )
            db.connections.close_all()

            logger.debug("Background importation callback done")

        async_import_archive()
