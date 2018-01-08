import re
import os
import sys
import json
import urllib
import argparse
import urllib.request as req
from urllib.parse import urlencode as urlencode


# chapter_pattern = re.compile(r'^(第(\d+)章\s+.*)')
chapter_pattern = re.compile(r'^((\d{3})、.*)')
text_to_convert = 'bsxcs.txt'
baidu_oauth_url = 'https://openapi.baidu.com/oauth/2.0/token?grant_type=client_credentials&client_id=%s&client_secret=%s&'
baidu_tsn_url = 'http://tsn.baidu.com/text2audio'
punctuations = u'[,;"!?…？。，：“”！ ]'
output_folder_txt = 'contents'
output_folder_mp3 = 'mp3'


def get_token(client_id, client_secret):
    url = baidu_oauth_url % (client_id, client_secret)

    with req.urlopen(url) as f:
        resp = f.read()
        resp = resp.decode('utf-8')
        resp = json.loads(resp)
        return resp['access_token']


def text2audio(txt, token, speed, volume, person, name):
    txt = urllib.parse.quote_plus(urllib.parse.quote_plus(txt))
    token = urllib.parse.quote_plus(urllib.parse.quote_plus(token))
    content = "tex=%s&lan=zh&cuid=client01&ctp=1&tok=%s&spd=%s&vol=%s&per=%s" % (
        txt, token, speed, volume, person)
    encoded = content.encode('utf-8')
    failed_count = 0
    while failed_count < 3:
        try:
            request = req.Request(baidu_tsn_url, encoded)
            with req.urlopen(request, timeout=10) as f:
                if f.status != 200:
                    print(
                        "failed to convert %s, server response code is %s", name, f.status)
                with open(name, 'wb') as lf:
                    lf.write(f.read())
        except KeyboardInterrupt as e:
            raise e
        except Exception as e:
            print('failed to convert %s.' % name)
            print('%s' % e)
            failed_count += 1
            print('Retrying...')
        else:
            break
    else:
        raise Exception("Failed to convert text to audio")


def split_chapters(file_orig, output_folder, chapter_pattern, encoding):
    with open(file_orig, 'rb') as f:
        content = f.read().decode(encoding)
        contents = content.split('\n')
        txt = []
        file_name = ''
        output_files = []
        for line in contents:
            line = line.strip()
            match = chapter_pattern.match(line)
            if match:
                if txt and file_name:
                    with open(os.path.join(output_folder, file_name), 'wb') as cf:
                        cf.write('\n'.join(txt).encode('utf-8'))
                        output_files.append(file_name)
                file_name = line + '.txt'
                txt = [line + '。']
            else:
                txt.append(line)
        if txt and file_name:
            with open(os.path.join(output_folder, file_name), 'wb') as cf:
                cf.write('\n'.join(txt).encode('utf-8'))
                output_files.append(file_name)
    return output_files


def get_prev_sp(txt, end_pos):
    if end_pos > len(txt) - 1:
        end_pos = len(txt) - 1
    end_pos -= 1
    while end_pos > 0 and txt[end_pos] not in punctuations:
        end_pos -= 1
    return end_pos


# txt is unicode
def split_txt(txt, limit=1024):
    txt = txt.strip()
    txt = txt.replace('\n', '')
    start_pos = 0
    splits = []
    count = 0
    while start_pos < len(txt):
        end_pos = len(txt)
        candidate = txt[start_pos: end_pos]
        split = candidate.encode('utf-8')

        # while len(split) > limit:
        while len(candidate.encode('gbk')) > limit:   # 尝试使用gbk的编码来计算长度
            end_pos = get_prev_sp(txt, end_pos)
            candidate = txt[start_pos: end_pos]
            split = candidate.encode('utf-8')

        splits.append(candidate.encode('utf-8'))
        start_pos += len(candidate)
        count += 1
        if count > 50:
            raise Exception("Infinite Loop?")
    return splits


def merge_mp3(from_files, dest_file):
    from_files = ['"%s"' % filename for filename in from_files]
    src_files = ' '.join(from_files)

    cmd = 'cat ' + src_files + ' >"' + dest_file + '"'
    os.system(cmd)
    cmd = 'rm ' + src_files
    os.system(cmd)


def merge_chapter_mp3(output_files, mp3_folder, mp3_prefix, max_index_len=3):
    index_format = '%0' + '%d' % max_index_len + 'd'
    mp3_format = '%s' + index_format + '_' + index_format + '.mp3'
    dest_file = os.path.join(
        mp3_folder, mp3_format % (
            mp3_prefix, output_files[0][1], output_files[-1][1]))
    from_files = [item[0] for item in output_files]
    merge_mp3(from_files, dest_file)


def convert_chapters(
        chapters, token, txt_folder, mp3_folder, mp3_prefix,
        chapters_per_file=20, chapter_start_index=1, chapter_end_index=None,
        speed=5, volume=5, person=0):
    output_files = []
    if not chapter_end_index:
        chapter_end_index = 2 ** 32
    for i, filename in enumerate(chapters):
        index = i + 1
        if index >= chapter_start_index and index <= chapter_end_index:
            txt_filename = os.path.join(txt_folder, filename)
            with open(txt_filename, 'rb') as f:
                txt = f.read().decode('utf-8')
                print('Split for %s' % filename)
                splits = split_txt(txt)
                print('Split done')
                small_mp3s = []
                for i, split in enumerate(splits):
                    split_mp3_filename = os.path.join(
                        mp3_folder, '%s_%s.mp3' % (filename[:-4], i))
                    print('Converting %s' % split_mp3_filename)
                    text2audio(split, token, speed, volume, person, split_mp3_filename)
                    print('Converting done')
                    small_mp3s.append(split_mp3_filename)
            chapter_mp3 = os.path.join(mp3_folder, '%s.mp3' % filename[:-4])
            merge_mp3(small_mp3s, chapter_mp3)
            output_files.append((chapter_mp3, index))
            if len(output_files) >= chapters_per_file:
                merge_chapter_mp3(output_files, mp3_folder, mp3_prefix)
                output_files = []

    if len(output_files) > 0:
        merge_chapter_mp3(output_files, mp3_folder, mp3_prefix)


def get_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--book', help='text book to be convert', required=True)
    parser.add_argument('--id', help='client id', required=True)
    parser.add_argument('--secret', help='client secret', required=True)
    parser.add_argument('--start', help='start chapter index', type=int, default=1)
    parser.add_argument('--end', help='end chapter index', type=int, default=None)
    parser.add_argument('--chapters', help='number of chapters per one mp3 file', type=int, default=5)
    parser.add_argument('--output', help='output mp3 folder', default='mp3')
    parser.add_argument('--speed', help='voice speed', type=int, default=5)
    parser.add_argument('--volume', help='voice volume', type=int, default=5)
    parser.add_argument('--person', help='person style', type=int, choices=[0, 1, 2, 3, 4])
    parser.add_argument('--encoding', help='text encoding', default='gbk')
    parser.add_argument('--mp3prefix', help='filename prefix of output mp3s', default='tts')

    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = get_arguments()
    txt_book = args.book
    client_id = args.id
    client_secret = args.secret

    if not os.path.isfile(txt_book):
        print('Invalid book flie')
        sys.exit(1)
    try:
        token = get_token(client_id, client_secret)
    except urllib.error.HTTPError:
        print("Invalid id or secret")
        sys.exit(1)
    if os.path.exists(args.output) and not os.path.isdir(args.output):
        print('Invalid output folder')
        sys.exit(1)
    if not os.path.exists(args.output):
        os.mkdir(args.output)

    chapters = split_chapters(
        args.book, output_folder_txt,
        chapter_pattern, encoding=args.encoding)

    convert_chapters(chapters, token, output_folder_txt,
                     args.output, chapters_per_file=args.chapters,
                     mp3_prefix=args.mp3prefix,
                     chapter_start_index=args.start, chapter_end_index=args.end,
                     speed=args.speed, volume=args.volume, person=args.person)
