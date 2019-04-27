# xtts
为中文小说生成语音朗读mp3

Convert Chinese Text novels to mp3 using Baidu AI API

本人是听书的爱好者，但是有很多小说，并找不到真人朗读的版本。而且有时候真人朗读反而会和你脑补的意境不同，影响听书的心情。反而是这种机器合成的声音，中性无特别的个性和情感，适应性更广。本人用此工具生成了数百小时的音频，成功的让自己的眼睛得到了相应时间的休息。

你需要首先申请百度AI的账号，目前百度语音合成的API是免费的。申请完毕后，在代码中填入你的账号信息。另外需要提供小说章节的正则表达式，以便按照章节来进行语音合成。只支持Python3，python2的时代过去了。

建议使用播客的客户端来播放生成的mp3，这样能记住播放的位置。特别推荐Overcast，upload功能简直是天作之合。

使用示例
`python3 tts.py --book "dmwf.txt" --mp3prefix 大明武夫 --pattern "^第.*章\\s+.*" --id 你的API_KEY --secret 你的Secret_Key --speed 8 --person 0 --encoding utf8 --output mp3`


