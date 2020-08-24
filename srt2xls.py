import xlsxwriter
import re
import logging

def parse_subtitles(lines):
    line_index = re.compile('^\d*$')
    line_timestamp = re.compile('^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}$')
    line_seperator = re.compile('^\s*$')

    current_record = {'index':None, 'timestamp':None, 'subtitles':[]}
    state = 'seeking to next entry'

    for line in lines:
        line = line.strip('\n')
        if state == 'seeking to next entry':
            if line_index.match(line):
                logging.debug('Found index: {i}'.format(i=line))
                current_record['index'] = line
                state = 'looking for timestamp'
            else:
                logging.error('HUH: Expected to find an index, but instead found: [{d}]'.format(d=line))

        elif state == 'looking for timestamp':
            if line_timestamp.match(line):
                logging.debug('Found timestamp: {t}'.format(t=line))
                current_record['timestamp'] = line
                state = 'reading subtitles'
            else:
                logging.error('HUH: Expected to find a timestamp, but instead found: [{d}]'.format(d=line))

        elif state == 'reading subtitles':
            if line_seperator.match(line):
                logging.info('Blank line reached, yielding record: {r}'.format(r=current_record))
                yield current_record
                state = 'seeking to next entry'
                current_record = {'index':None, 'timestamp':None, 'subtitles':[]}
            else:
                logging.debug('Appending to subtitle: {s}'.format(s=line))
                current_record['subtitles'].append(line)

        else:
            logging.error('HUH: Fell into an unknown state: `{s}`'.format(s=state))
    if state == 'reading subtitles':
        # We must have finished the file without encountering a blank line. Dump the last record
        yield current_record

def write_dict_to_worksheet(columns_for_keys, keyed_data, worksheet, row):
    """
    Write a subtitle-record to a worksheet.
    Return the row number after those that were written (since this may write multiple rows)
    """
    current_row = row
    #First, horizontally write the entry and timecode
    for (colname, colindex) in columns_for_keys.items():
        if colname != 'subtitles':
            worksheet.write(current_row, colindex, keyed_data[colname])

    #Next, vertically write the subtitle data
    subtitle_column = columns_for_keys['subtitles']
    for morelines in keyed_data['subtitles']:
        worksheet.write(current_row, subtitle_column, morelines)
        current_row+=1

    return current_row

def convert(input_filename, output_filename):
    workbook = xlsxwriter.Workbook(output_filename)
    worksheet = workbook.add_worksheet('subtitles')
    columns = {'index':0, 'timestamp':1, 'subtitles':2}

    next_available_row = 0
    records_processed = 0
    headings = {'index':"Entries", 'timestamp':"Timecodes", 'subtitles':["Subtitles"]}
    next_available_row=write_dict_to_worksheet(columns, headings, worksheet, next_available_row)

    with open(input_filename) as textfile:
        for record in parse_subtitles(textfile):
            next_available_row = write_dict_to_worksheet(columns, record, worksheet, next_available_row)
            records_processed += 1

    print('Done converting {inp} to {outp}. {n} subtitle entries found. {m} rows written'.format(inp=input_filename, outp=output_filename, n=records_processed, m=next_available_row))
    workbook.close()

convert(input_filename='subtitles.srt', output_filename='Subtitle.xlsx')
