import sys
import copy
import json
from datetime import datetime

from scripts.migrate_piwik import utils
from scripts.migrate_piwik import settings


def main():

    history_run_id = utils.get_history_run_id_for('transform01')
    complaints_run_id = utils.get_complaints_run_id_for('transform01')
    if history_run_id != complaints_run_id:
        print("You need to validate your first-phase transformed data! Bailing...")
        sys.exit()

    extract_complaints = utils.get_complaints_for('transform01', 'r')
    extract_complaints.readline()  # toss header
    if extract_complaints.readline() is not None:
        print("You have unaddressed complaints in your first-phase transform! Bailing...")
        sys.exit()

    history_file = utils.get_history_for('transform02', 'w')
    history_file.write('Run ID: {}\n'.format(complaints_run_id))
    history_file.write('Beginning extraction at: {}Z\n'.format(datetime.utcnow()))

    transform_dir = utils.get_dir_for('transform02')
    public_template = transform_dir + '/public-{0:04d}.data'
    private_template = transform_dir + '/private-{0:04d}.data'

    linenum = 0
    batchnum = 0
    public_pageviews = []
    private_pageviews = []
    input_file = open(utils.get_dir_for('transform01') + '/' + settings.TRANSFORM01_FILE, 'r')
    for pageview_json in input_file.readlines():
        linenum += 1
        if not linenum % 1000:
            print('Batching line {}'.format(linenum))

        pageview = json.loads(pageview_json)
        private_pageviews.append(pageview)

        public_pageview = copy.deepcopy(pageview)
        del public_pageview['user']['id']
        del public_pageview['tech']['ip']
        for addon in public_pageview['keen']['addons']:
            if addon['name'] == 'keen:ip_to_geo':
                public_pageview['keen']['addons'].remove(addon)
        public_pageviews.append(public_pageview)

        if linenum % settings.BATCH_SIZE == 0:
            batchnum += 1
            write_batch(batchnum, complaints_run_id, public_template, public_pageviews)
            write_batch(batchnum, complaints_run_id, private_template, private_pageviews)
        
    if linenum % settings.BATCH_SIZE != 0:
        batchnum += 1
        write_batch(batchnum, complaints_run_id, public_template, public_pageviews)
        write_batch(batchnum, complaints_run_id, private_template, private_pageviews)

    history_file.write('Batch Count: {}\n'.format(batchnum))


def write_batch(batchnum, run_id, template, pageviews):
    print("---Writing Batch")
    batch_file = open(template.format(batchnum), 'w')
    batch_file.write('Run ID: {}\n'.format(run_id))
    batch_file.write(json.dumps(pageviews))
    del pageviews[:]


if __name__ == "__main__":
    main()
