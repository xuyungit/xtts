import re
import os
import sys
import json
import urllib
import argparse
import urllib.request as req
from urllib.parse import urlencode as urlencode
chardet_available = False
try:
    import chardet
    chardet_available = True
except ModuleNotFoundError:
    pass

# chapter_pattern = re.compile(r'^(第(\d+)章\s+.*)')
# chapter_pattern = re.compile(r'^((\d{3})、.*)')
# chapter_pattern = re.compile(r'^(第(\d{3})回、.*)')
# chapter_pattern = re.compile(r'^(第(\d{4})章\s+.*)')
# chapter_pattern = re.compile(r'^(第.+章\s+.*)')
chapter_pattern = re.compile(r'^(第\d+章\s+.*)')
text_to_convert = 'bsxcs.txt'
baidu_oauth_url = 'https://openapi.baidu.com/oauth/2.0/token?grant_type=client_credentials&client_id=%s&client_secret=%s&'
baidu_tsn_url = 'http://tsn.baidu.com/text2audio'
punctuations = u'[,;"!?…？。，；：“”！ ]'
sentence_sep = re.compile(r'[。！；;!?. ]')
output_folder_txt = 'contents'
output_folder_mp3 = 'mp3'


def get_token(client_id, client_secret):
    url = baidu_oauth_url % (client_id, client_secret)

    with req.urlopen(url) as f:
        resp = f.read()
        resp = resp.decode('utf-8')
        resp = json.loads(resp)
        return resp['access_token']

def make_sentence_shorter(txt, start, stop):
    # print(start, stop)
    # print('-' * 100)
    # print(txt[start:stop])
    # print('^' * 100)
    if stop - start > 200:
        sentence = txt[start:stop]
        sentence = sentence.replace(',', '.')
        sentence = sentence.replace('，', '。')
        txt = txt[:start] + sentence + txt[stop:]
        # print(sentence)
    return txt


def handle_long_sentence(txt):
    new_txt = txt.replace('……', '。')
    if new_txt != txt:
        return new_txt

    sentence_start = 0
    for i, char in enumerate(txt):
        if char in '.;?!。；？！':
            txt = make_sentence_shorter(txt, sentence_start, i)
            sentence_start = i
    txt = make_sentence_shorter(txt, sentence_start, i)
    return txt


def text2audio(txt, token, speed, volume, person, name):
    txt_org = txt
    txt = urllib.parse.quote_plus(txt)
    # txt = urllib.parse.quote_plus(urllib.parse.quote_plus(txt))
    failed_count = 0
    while failed_count < 3:
        token = urllib.parse.quote_plus(urllib.parse.quote_plus(token))
        content = "tex=%s&lan=zh&cuid=client01&ctp=1&tok=%s&spd=%s&vol=%s&per=%s" % (
            txt, token, speed, volume, person)
        encoded = content.encode('utf-8')
        try:
            request = req.Request(baidu_tsn_url, encoded)
            with req.urlopen(request, timeout=10) as f:
                if f.status != 200:
                    print(
                        "failed to convert %s, server response code is %s", name, f.status)
                    print('Response from server is %s\n%s' % (f.status, f.read()))
                    exit(1)
                if 'audio/mp3' != f.getheader('Content-Type'):
                    ret = f.read().decode('utf-8')
                    print("Something wrong with tts API call!")
                    print('Response from server is %s' % ret)                    
                    print('-' * 100)
                    print(txt_org)
                    print('-' * 100)
                    ret_detail = json.loads(ret)
                    # {"err_detail":"Invalid text length","err_msg":"tex param err","err_no":513,"err_subcode":234,"tts_logid":1024616872}
                    # 单句过长
                    if ret_detail['err_no'] == 513 and ret_detail['err_subcode'] == 234:
                        txt_org = handle_long_sentence(txt_org)
                        txt = txt_org
                        txt = urllib.parse.quote_plus(txt)
                        failed_count += 1
                        continue

                    exit(1)
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
        content = f.read().decode(encoding, errors='ignore')
        contents = content.split('\n')
        txt = []
        file_name = ''
        output_files = []
        for line in contents:
            line = line.strip()
            match = chapter_pattern.match(line)
            if match:
                if txt and not file_name:
                    file_name = '引子.txt'
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
def split_txt(txt, limit=2000):
    txt = txt.strip()
    txt = txt.replace('\n', '')
    start_pos = 0
    splits = []
    count = 0
    while start_pos < len(txt):
        end_pos = len(txt)
        candidate = txt[start_pos: end_pos]
        while len(candidate) > limit:
            end_pos = get_prev_sp(txt, end_pos)
            candidate = txt[start_pos: end_pos]

        splits.append(candidate)
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
    parser.add_argument('--book', help='待合成的小说文本文件名', required=True)
    parser.add_argument('--id', help='你的百度API Key', required=True)
    parser.add_argument('--secret', help='你的百度Secret Key', required=True)
    parser.add_argument('--start', help='从小说的哪一章开始', type=int, default=1)
    parser.add_argument('--end', help='到小说的哪一章停止', type=int, default=None)
    parser.add_argument('--chapters', help='每个mp3文件包含几章', type=int, default=5)
    parser.add_argument('--output', help='输出的mp3保存目录', default='mp3')
    parser.add_argument('--speed', help='语速', type=int, default=5)
    parser.add_argument('--volume', help='音量', type=int, default=5)
    parser.add_argument('--person', help='人', type=int, choices=[0, 1, 2, 3, 4, 5, 106, 110, 111, 103], default=0)
    parser.add_argument('--encoding', help='可指定文件的编码', default='')
    parser.add_argument('--mp3prefix', help='输出的mp3文件的前缀', default='tts')
    parser.add_argument('--pattern', help='章节名称的正则（用来切分章节）', default=r'^第.*章\s+.*')

    args = parser.parse_args()
    return args


def detect_code(txt_filename):
    result = "ascii"
    if not chardet_available:
        return result
    try:
        with open(txt_filename, 'rb') as f:
            txt_snippet = f.read(1024)
        ret = chardet.detect(txt_snippet)
        if ret and ret['confidence'] > 0.9:
            result = ret['encoding']
        else:
            print('Cannot detect encoding with enough confidence')
    except Except as e:
        print('Something wrong with checking file encoding:', e)
        pass
    return result


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
    except:
        print("Invalid id or secret")
        sys.exit(1)
    if os.path.exists(args.output) and not os.path.isdir(args.output):
        print('Invalid output folder')
        sys.exit(1)
    if os.path.exists(output_folder_txt) and not os.path.isdir(output_folder_txt):
        print('Invalid output folder')
        sys.exit(1)
    if not os.path.exists(args.output):
        os.mkdir(args.output)
    if not os.path.exists(output_folder_txt):
        os.mkdir(output_folder_txt)

    print(chardet_available)
    if not args.encoding and chardet_available:
        print("File encoding is not specified, now try to detect file encoding...")
        encoding_detect = detect_code(args.book)
        print("Detected encoding is", encoding_detect)
    elif not args.encoding:
        encoding_detect = 'gbk'
        print("File encoding is not specified, use default 'gbk' encoding!")
    else:
        encoding_detect = args.encoding
    chapter_pattern = re.compile(args.pattern)
    print(args.pattern)
    print('Spliting chapters using encoding %s...' % encoding_detect)
    chapters = split_chapters(
        args.book, output_folder_txt,
        chapter_pattern, encoding=encoding_detect)
    print('%s chapters splited' % len(chapters))

    convert_chapters(chapters, token, output_folder_txt,
                     args.output, chapters_per_file=args.chapters,
                     mp3_prefix=args.mp3prefix,
                     chapter_start_index=args.start, chapter_end_index=args.end,
                     speed=args.speed, volume=args.volume, person=args.person)
