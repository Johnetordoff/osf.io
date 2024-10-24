import csv
import io
import json
from api.base.settings.defaults import USER_INSTITUTION_REPORT_FILENAME, MAX_SIZE_OF_ES_QUERY
import datetime

from django.http import Http404

from rest_framework import renderers


# put these fields first, then sort the rest alphabetically
PRIORITIZED_FIELDNAMES = {'report_date', 'report_yearmonth', 'timestamp'}
def csv_fieldname_sortkey(fieldname):
    return (
        (fieldname not in PRIORITIZED_FIELDNAMES),  # False ordered before True
        fieldname,
    )


def get_nested_keys(report_attrs):
    """
    Recursively retrieves all nested keys from the report attributes.
    Handles both dictionaries and lists of attributes.
    """
    if isinstance(report_attrs, dict):
        for attr_key in sorted(report_attrs.keys(), key=csv_fieldname_sortkey):
            attr_value = report_attrs[attr_key]
            if isinstance(attr_value, dict):
                for subkey in get_nested_keys(attr_value):
                    yield f'{attr_key}.{subkey}'
            else:
                yield attr_key
    elif isinstance(report_attrs, list):
        for item in report_attrs:
            yield from get_nested_keys(item)


def get_key_value(nested_key, report_attrs):
    report_attrs = report_attrs.to_dict() if hasattr(report_attrs, 'to_dict') else report_attrs
    (key, _, next_nested_key) = nested_key.partition('.')
    attr_value = report_attrs.get(key, {})
    return (
        get_key_value(next_nested_key, attr_value)
        if next_nested_key
        else attr_value
    )


def get_csv_row(keys_list, report_attrs):
    return [
        get_key_value(key, report_attrs)
        for key in keys_list
    ]


class MetricsReportsBaseRenderer(renderers.BaseRenderer):
    media_type: str
    format: str
    CSV_DIALECT: csv.Dialect
    extension: str

    def get_filename(self, renderer_context: dict, format_type: str) -> str:
        """Generate the filename for the CSV/TSV file based on institution and current date."""
        if renderer_context and 'view' in renderer_context:
            current_date = datetime.datetime.now().strftime('%Y-%m')  # Format as 'YYYY-MM'
            return USER_INSTITUTION_REPORT_FILENAME.format(
                date_created=current_date,
                institution_id=renderer_context['view'].kwargs['institution_id'],
                format_type=format_type,
            )
        else:
            raise NotImplementedError('Missing format filename')

    def get_all_data(self, view, request):
        """Bypass pagination by fetching all the data."""
        view.pagination_class = None  # Disable pagination
        return view.get_default_search().extra(size=MAX_SIZE_OF_ES_QUERY).execute()

    def render(self, data: dict, accepted_media_type: str = None, renderer_context: dict = None) -> str:
        """Render the full dataset as CSV or TSV format."""
        data = self.get_all_data(renderer_context['view'], renderer_context['request'])
        hits = data.hits
        if not hits:
            raise Http404('<h1>none found</h1>')

        # Assuming each hit contains '_source' with the relevant data
        first_row = hits[0].to_dict()
        csv_fieldnames = list(first_row)
        csv_filecontent = io.StringIO(newline='')
        csv_writer = csv.writer(csv_filecontent, dialect=self.CSV_DIALECT)
        csv_writer.writerow(csv_fieldnames)

        # Write each hit's '_source' as a row in the CSV
        for hit in hits:
            csv_writer.writerow(get_csv_row(csv_fieldnames, hit.to_dict()))

        # Set response headers for file download
        response = renderer_context['response']
        filename = self.get_filename(renderer_context, self.extension)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return csv_filecontent.getvalue()


class MetricsReportsCsvRenderer(MetricsReportsBaseRenderer):
    media_type = 'text/csv'
    format = 'csv'
    CSV_DIALECT = csv.excel
    extension = 'csv'


class MetricsReportsTsvRenderer(MetricsReportsBaseRenderer):
    media_type = 'text/tab-separated-values'
    format = 'tsv'
    CSV_DIALECT = csv.excel_tab
    extension = 'tsv'


class MetricsReportsJsonRenderer(MetricsReportsBaseRenderer):
    media_type = 'application/json'
    format = 'json_file'
    extension = 'json'

    def default_serializer(self, obj):
        """Custom serializer to handle non-serializable objects like datetime."""
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()  # Convert datetime to ISO format string
        raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """Render the response as JSON format and trigger browser download as a binary file."""
        data = self.get_all_data(renderer_context['view'], renderer_context['request'])
        hits = data.hits
        if not hits:
            raise Http404('<h1>none found</h1>')

        serialized_hits = [hit.to_dict() for hit in hits]

        # Set response headers for file download
        response = renderer_context['response']
        filename = self.get_filename(renderer_context, self.extension)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        # Use custom serializer for non-serializable types (like datetime)
        return json.dumps(serialized_hits, default=self.default_serializer, indent=4).encode('utf-8')
