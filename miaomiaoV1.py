import json
import os
import traceback
import uuid
from copy import deepcopy
from flask import request, Flask
import openai
import requests
import tiktoken

class Miaomiao:

    def __init__(self, __name__):
        self.sessions={}
        self.configfile = "config_miaomiao.json"
        self.get_config()
        self.admin_qq = self.configdata['qq_bot']['admin_qq'].keys()
        self.miaomiao_qq = self.configdata['qq_bot']['qq_no']
        
        openai.api_base = "https://chat-gpt.aurorax.cloud/v1"

        

    def get_config(self):
        with open(self.configfile, "r",
              encoding='utf-8') as jsonfile:
            config_data = json.load(jsonfile)
        self.configdata = config_data
        return config_data
    
    
    
    def miaomiao_called(self, text):
        if str("[CQ:at,qq=%s]" % self.miaomiao_qq) in text or "喵喵" in text:
            return True
        else:
            return False

    def process_groupmsg(self, msg_text, gid, sender_uid, sender_uname):
        config = self.get_config()
        if not self.miaomiao_called(msg_text):
            return False
        
        # check enabled
        if not "G%s"%(str(gid)) in config['enabled'].keys():
            return False        
        if not config['enabled']["G%s"%(str(gid))] == 'enabled':
            return False
        


        return True

    def process_privatemsg(self, msg_text, sender_uid, sender_uname):
        try:
            sid = "P%s"%(str(sender_uid))
            config = self.get_config()
            if not self.miaomiao_called(msg_text):
                return False
            
            # check enabled
            if not sid in config['enabled'].keys():
                return False        
            if not config['enabled'][sid] == 'enabled':
                return False
            
            msg_text = str(msg_text).replace(str("[CQ:at,qq=%s]" % self.configdata), '')
            msg_text = str(msg_text).replace(("@喵喵"), '')
            
            if sender_uid in config['admin_qq'].keys():

            # admin专用功能
                print(0)

            # special commands
            if msg_text.lstrip().startswith("喵喵记忆清除"):
                del self.sessions[sender_uid]['msg'][1:]
                return None
            
            if msg_text.lstrip().startswith("切换喵喵"):
                _, miaomiao_type = msg_text.lstrip().split(" ")
                flag = self.set_char(sid, miaomiao_type)
                if not flag:
                    self.send_private_message(sender_uid, "没有这种喵喵哦")
                else:
                    self.send_private_message(sender_uid, "现在的喵喵是：%s 哦"%(miaomiao_type))
                return None
            
            if msg_text.lstrip().startswith("自定义喵喵"):
                try:
                    _, label, description = msg_text.lstrip().split(" ")
                    self.user_create_character(sid, label, description)
                    self.send_private_message(sender_uid, "自定义喵喵:%s制作成功哦"%(label))
                    return None
                except:
                    self.send_private_message(sender_uid, "自定义喵喵:%s没有成功哦"%(label))
                    return None
                
            if msg_text.lstrip().startswith("debug"):
                output = ""
                output += "sid: %s\n" %(sid)
                output += "sid"

            self.get_session(sid)
            self.sessions[sid]['msg'].append({"role": "user", "content": msg_text})
            if len(self.sessions[sid]['msg']) >= 13:
                del self.sessions[sid]['msg'][1:3]
            gpt_response = self.chat_with_gpt(self.sessions[sid]['msg'])
            if_output_failed = self.output_failed(gpt_response)
            self.send_private_message(sender_uid, gpt_response)
            self.sessions[sid]['msg'].append({"role": "assistant", "content": gpt_response})

        except Exception as error:
            traceback.print_exc()
            return str('异常: ' + str(error))

    def set_char(self, sid, miaomiao_type=False):
        self.get_config()
        if not miaomiao_type:
            self.sessions[sid]['chara'] = self.configdata['chat_chara'][sid]
            self.sessions[sid]['msg'] = [{"role": "system", "content": self.configdata['public_miaomiao'][self.sessions[sid]['chara']]}]
        else:
            if miaomiao_type in self.configdata['public_miaomiao'].keys():
                self.sessions[sid]['chara'] = miaomiao_type
                self.sessions[sid]['msg'] = [{"role": "system", "content": self.configdata['public_miaomiao'][miaomiao_type]}]
            elif sid[1:] in self.configdata['admin_qq'] and miaomiao_type in self.configdata['private_miaomiao'].keys():
                self.sessions[sid]['chara'] = miaomiao_type
                self.sessions[sid]['msg'] = [{"role": "system", "content": self.configdata['private_miaomiao'][miaomiao_type]}]
            else:
                return False    
        return True
    
    def user_create_character(self, sid, label, description):
        self.sessions[sid]['chara'] = label
        del self.sessions[sid]['msg'][1:]
        self.sessions[sid]['msg'][0] = deepcopy({
            "role":"system",
            "content": description
        })
        return None
    
    # 检测输出是否报错
    def output_failed(self, msg):
        if "Rate limit reached for" in msg:
            return 1
        elif "Error communicating with OpenAI" in msg:
            return 2
        elif "The server had an error processing your request." in msg:
            return 2
        elif "Request timed out: HTTPSConnectionPool" in msg:
            return 2
        elif "4096" in msg:
            return 3
        return 0

    def get_session(self, sid):
        config = self.get_config()
        if sid not in self.sessions.keys():
            if sid in config['chat_chara'].keys():
                chara = config['chat_chara'][sid]
            else:
                chara = self.configdata['default_chara']
                chat_chara = self.configdata['chat_chara']
                chat_chara[sid] = chara
                self.configdata.update({'chat_chara': chat_chara})
                with open(self.configfile, 'w', encoding='utf-8') as jsonfile:
                    json.dump(self.configdata, jsonfile, indent=4,ensure_ascii=False)
            self.sessions[sid] = {
                'chara_name': chara,
                'chara_text': self.configdata['public_miaomiao'][chara],
                'msg': [
                        {
                            "role": "system", 
                            "content": self.configdata['public_miaomiao'][chara]
                        }
                    ]
                }
        return self.sessions[sid]
    
    def chat_with_gpt(self, messages):
        try:
            self.get_config()
            if not self.configdata['openai']['api_key']:
                return "请设置Api Key"
            else:
                openai.api_key = self.configdata['openai']['api_key']
            resp = openai.ChatCompletion.create(
                model=self.configdata['chatgpt']['model'],
                messages=messages
            )
            resp = resp['choices'][0]['message']['content']
        except openai.OpenAIError as e:
            print('openai 接口报错: ' + str(e))
            resp = str(e)
        return resp
    
    # 发送私聊消息方法 uid为qq号，message为消息内容
    def send_private_message(self, uid, message):
        try:
            self.get_config()
            #if len(message) >= get_config()['qq_bot']['max_length']:  # 如果消息长度超过限制，转成图片发送
            #    pic_path = genImg(message)
            #    message = "[CQ:image,file=" + pic_path + "]"
            res = requests.post(url=self.configdata['qq_bot']['cqhttp_url'] + "/send_private_msg",
                                params={'user_id': int(uid), 'message': message}).json()
            if res["status"] == "ok":
                print("私聊消息发送成功")
            else:
                print(res)
                print("私聊消息发送失败，错误信息：" + str(res['wording']))

        except Exception as error:
            print("私聊消息发送失败")
            print(error)

    # 发送群消息方法
    def send_group_message(self, gid, message, uid):
        try:
            #if len(message) >= get_config()['qq_bot']['max_length']:  # 如果消息长度超过限制，转成图片发送
            #    pic_path = genImg(message)
            #    message = "[CQ:image,file=" + pic_path + "]"
            message = str('[CQ:at,qq=%s]\n' % uid) + message  # @发言人
            res = requests.post(url=self.configdata['qq_bot']['cqhttp_url'] + "/send_group_msg",
                                params={'group_id': int(gid), 'message': message}).json()
            if res["status"] == "ok":
                print("群消息发送成功")
            else:
                print("群消息发送失败，错误信息：" + str(res['wording']))
        except Exception as error:
            print("群消息发送失败")
            print(error)

if __name__ == '__main__':
    miaomiao = Miaomiao(__name__)
    # 监听QQ消息
    server = Flask(__name__)
    @server.route('/', methods=["POST"])
    def get_message():
        msg = request.get_json()
        msg_type = msg.get('message_type')
        msg_text = msg.get('raw_message')
        sender = msg.get('sender')
        sender_uid = sender.get('user_id')
        sender_uname = sender.get('nickname')
        if msg_type == 'group':
            gid = msg.get('group_id')
            miaomiao.process_groupmsg(msg_text, gid, sender_uid, sender_uname)
        elif msg_type == 'private':
            miaomiao.process_privatemsg(msg_text, sender_uid, sender_uname)
        return "ok"
    
    server.run(port=5555, host='0.0.0.0', use_reloader=False)
