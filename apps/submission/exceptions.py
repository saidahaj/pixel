class ArchiveError(Exception):
    pass


class InvalidArchiveFormatError(ArchiveError):
    pass


class MetaFileRequiredError(ArchiveError):
    pass


class MetaFileFormatError(ArchiveError):
    pass


class MetaFileParsingError(ArchiveError):
    pass


class PixelSetParserError(Exception):
    pass


class PixelSetParserSaveError(PixelSetParserError):
    pass
