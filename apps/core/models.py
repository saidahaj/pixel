import uuid
import mptt

from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import ArrayField
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import ugettext as _
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel
from tagulous import models as tgl_models

from .mixins import UUIDModelMixin


class Species(models.Model):
    """Canonical species
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    name = models.CharField(
        _("Name"),
        max_length=100,
        unique=True,
    )

    reference = models.ForeignKey(
        'data.Entry',
        on_delete=models.CASCADE,
        related_name='species',
        related_query_name='species',
        blank=True,
        null=True,
    )

    repository = models.ForeignKey(
        'data.Repository',
        on_delete=models.CASCADE,
        related_name='species',
        related_query_name='species',
        blank=True,
        null=True,
    )

    description = models.TextField(
        _("Description"),
        blank=True,
    )

    class Meta:
        ordering = ('name', )
        verbose_name = _("Species")
        verbose_name_plural = _("Species")

    def __str__(self):
        return self.name


class Strain(models.Model):
    """Studied strains
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        _("Name"),
        max_length=100,
    )

    description = models.TextField(
        _("Description"),
        blank=True,
    )

    species = models.ForeignKey(
        'Species',
        on_delete=models.CASCADE,
        related_name='strains',
        related_query_name='strain',
    )

    reference = models.ForeignKey(
        'data.Entry',
        on_delete=models.CASCADE,
        related_name='strains',
        related_query_name='strain',
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ('name', )
        verbose_name = _("Strain")
        verbose_name_plural = _("Strains")
        unique_together = (
            ('name', 'species'),
        )

    def __str__(self):
        return self.name


class OmicsUnitType(models.Model):
    """Omics unit type could be promoter, gene, etc.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        _("Name"),
        max_length=100,
        unique=True,
    )

    description = models.TextField(
        _("Description"),
        blank=True,
    )

    class Meta:
        ordering = ('name', )
        verbose_name = _("Omics unit type")
        verbose_name_plural = _("Omics unit types")

    def __str__(self):
        return self.name


class OmicsUnit(UUIDModelMixin, models.Model):
    """The Omics Unit could be a gene, a promoter, etc.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    reference = models.ForeignKey(
        'data.Entry',
        on_delete=models.CASCADE,
    )

    strain = models.ForeignKey(
        'Strain',
        on_delete=models.CASCADE,
        related_name='omics_units',
        related_query_name='omics_unit',
    )

    type = models.ForeignKey(
        'OmicsUnitType',
        on_delete=models.CASCADE,
        related_name='omics_units',
        related_query_name='omics_unit',
    )

    STATUS_DUBIOUS = 1
    STATUS_EXISTS = 2
    STATUS_INVALID = 3
    STATUS_VALIDATED = 4
    STATUS_CHOICES = (
        (STATUS_DUBIOUS, _("Dubious")),
        (STATUS_EXISTS, _("Exists")),
        (STATUS_INVALID, _("Invalid")),
        (STATUS_VALIDATED, _("Validated")),
    )
    status = models.PositiveSmallIntegerField(
        _("Status"),
        choices=STATUS_CHOICES,
        default=STATUS_DUBIOUS,
    )

    class Meta:
        ordering = ('strain', 'reference')
        verbose_name = _("Omics Unit")
        verbose_name_plural = _("Omics Units")
        unique_together = (
            ('reference', 'strain', 'type')
        )

    def __str__(self):
        return '{} ({}/{}/{})'.format(
                self.get_short_uuid(),
                self.type,
                self.strain,
                self.strain.species.name
                )


class PixelSet(UUIDModelMixin, models.Model):
    """A pixelset is a collection of pixels for an analysis
    """

    def pixelset_upload_to(instance, filename):
        return '{}/analyses/{}/pixelsets/{}'.format(
            instance.analysis.pixeler.id,
            instance.analysis.id,
            filename
        )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    pixels_file = models.FileField(
        _("Pixels file"),
        upload_to=pixelset_upload_to,
        max_length=255,
    )

    description = models.TextField(
        _("Description"),
        blank=True,
    )

    cached_species = ArrayField(
        models.CharField(max_length=100, blank=False),
        default=list()
    )

    cached_omics_areas = ArrayField(
        models.CharField(max_length=100, blank=False),
        default=list()
    )

    cached_omics_unit_types = ArrayField(
        models.CharField(max_length=100, blank=False),
        default=list()
    )

    analysis = models.ForeignKey(
        'Analysis',
        on_delete=models.CASCADE,
        related_name='pixelsets',
        related_query_name='pixelset',
    )

    class Meta:
        ordering = ('analysis', 'pixels_file')
        verbose_name = _("Pixel set")
        verbose_name_plural = _("Pixel sets")

    def get_absolute_url(self):
        return reverse(
            'explorer:pixelset_detail',
            kwargs={'pk': str(self.id)}
        )

    def get_export_pixels_url(self):
        return reverse(
            'explorer:pixelset_export_pixels',
            kwargs={'pk': str(self.id)}
        )

    def get_omics_areas(self):
        # This method is extremely costly and that is why we have added the
        # `cached_omics_areas` field. This method is used for updating this
        # field rather than being used directly.
        return set(self.analysis.experiments.values_list(
            'omics_area__name',
            flat=True
        ))

    def get_omics_unit_types(self):
        # This method is extremely costly and that is why we have added the
        # `cached_omics_unit_types` field. This method is used for updating
        # this field rather than being used directly.
        return set(self.pixels.values_list(
            'omics_unit__type__name',
            flat=True
        ))

    def get_species(self):
        # This method is extremely costly and that is why we have added the
        # `cached_species` field. This method is used for updating this field
        # rather than being used directly.
        return set(self.pixels.values_list(
            'omics_unit__strain__species__name',
            flat=True
        ))

    def update_cached_fields(self):
        self.cached_species = list(self.get_species())
        self.cached_omics_unit_types = list(self.get_omics_unit_types())
        self.cached_omics_areas = list(self.get_omics_areas())
        self.save(
            update_fields=[
                'cached_species',
                'cached_omics_unit_types',
                'cached_omics_areas',
            ]
        )


class Pixel(UUIDModelMixin, models.Model):
    """A pixel is the smallest measurement unit for an Omics study
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    value = models.FloatField(
        _("Value"),
        help_text=_("The pixel value")
    )

    quality_score = models.FloatField(
        _("Quality score"),
        help_text=_("Could be a p-value, confidence index, etc."),
        null=True,
        blank=True,
    )

    omics_unit = models.ForeignKey(
        'OmicsUnit',
        on_delete=models.CASCADE,
        related_name='pixels',
        related_query_name='pixel',
    )

    pixel_set = models.ForeignKey(
        'PixelSet',
        on_delete=models.CASCADE,
        related_name='pixels',
        related_query_name='pixel',
    )

    class Meta:
        ordering = ('pixel_set', 'omics_unit')
        verbose_name = _("Pixel")
        verbose_name_plural = _("Pixels")


class Tag(tgl_models.TagTreeModel):
    """The Pixel tag model is mostly used to add facets to experiment search.
    """

    class TagMeta:
        force_lowercase = True


class Experiment(UUIDModelMixin, models.Model):
    """An experiment correspond to preliminary work on an OmicsUnit, _e.g._ a
    publication or preliminary work from a partnering laboratory.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    description = models.TextField(
        _("Description"),
        blank=True,
    )

    omics_area = mptt.fields.TreeForeignKey(
        'OmicsArea',
        on_delete=models.CASCADE,
        related_name='experiments',
        related_query_name='experiment',
    )

    entries = models.ManyToManyField(
        'data.Entry',
        related_name='experiments',
        related_query_name='experiment',
    )

    tags = tgl_models.TagField(
        to=Tag,
    )

    completed_at = models.DateField(
        _("Completion date"),
    )

    released_at = models.DateField(
        _("Release date"),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        editable=False,
    )

    saved_at = models.DateTimeField(
        auto_now=True,
        editable=False,
    )

    class Meta:
        ordering = ('completed_at', 'released_at')
        verbose_name = _("Experiment")
        verbose_name_plural = _("Experiments")


class Analysis(UUIDModelMixin, models.Model):
    """An analysis from a set of pixels
    """

    def secondary_data_upload_to(instance, filename):
        return '{}/analyses/{}/secondary_data/{}'.format(
            instance.pixeler.id,
            instance.id,
            filename
        )

    def notebook_upload_to(instance, filename):
        return '{}/analyses/{}/notebook/{}'.format(
            instance.pixeler.id,
            instance.id,
            filename
        )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    description = models.TextField(
        _("Description"),
        blank=True,
    )

    experiments = models.ManyToManyField(
        'Experiment',
        related_name='analyses',
        related_query_name='analysis',
    )

    secondary_data = models.FileField(
        _("Secondary data"),
        upload_to=secondary_data_upload_to,
        max_length=255,
    )

    notebook = models.FileField(
        _("Notebook"),
        help_text=_(
            "Upload your Jupiter Notebook or any other document helping to "
            "understand your analysis"
        ),
        blank=True,
        upload_to=notebook_upload_to,
        max_length=255,
    )

    pixeler = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='analyses',
        related_query_name='analysis',
    )

    tags = tgl_models.TagField(
        to=Tag,
    )

    completed_at = models.DateField(
        _("Completion date"),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        editable=False,
    )

    saved_at = models.DateTimeField(
        auto_now=True,
        editable=False,
    )

    class Meta:
        ordering = ('pixeler', 'completed_at')
        verbose_name = _("Analysis")
        verbose_name_plural = _("Analyses")


class OmicsArea(MPTTModel):
    """Omics Area (Tree)
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        _("Name"),
        max_length=100,
        unique=True,
    )

    description = models.TextField(
        _("Description"),
        blank=True,
    )

    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        db_index=True
    )

    class Meta:
        ordering = ('name', )
        verbose_name = _("Omics area")
        verbose_name_plural = _("Omics areas")

    class MPTTMeta:
        order_insertion_by = ['name']

    def __str__(self):
        return str(self.name)


class Pixeler(AbstractUser):
    """Pixel database user
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    class Meta:
        verbose_name = _("Pixeler")
        verbose_name_plural = _("Pixelers")
