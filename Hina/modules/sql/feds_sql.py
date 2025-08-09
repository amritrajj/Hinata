import ast
import asyncio

from .db_connection import BASE, async_session
from sqlalchemy import Boolean, Column, Integer, String, UnicodeText
from telegram.error import BadRequest, TelegramError
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, delete


class Federations(BASE):
    __tablename__ = "feds"
    owner_id = Column(String(14))
    fed_name = Column(UnicodeText)
    fed_id = Column(UnicodeText, primary_key=True)
    fed_rules = Column(UnicodeText)
    fed_log = Column(UnicodeText)
    fed_users = Column(UnicodeText)

    def __init__(self, owner_id, fed_name, fed_id, fed_rules, fed_log, fed_users):
        self.owner_id = owner_id
        self.fed_name = fed_name
        self.fed_id = fed_id
        self.fed_rules = fed_rules
        self.fed_log = fed_log
        self.fed_users = fed_users


class ChatF(BASE):
    __tablename__ = "chat_feds"
    chat_id = Column(String(14), primary_key=True)
    chat_name = Column(UnicodeText)
    fed_id = Column(UnicodeText)

    def __init__(self, chat_id, chat_name, fed_id):
        self.chat_id = chat_id
        self.chat_name = chat_name
        self.fed_id = fed_id


class BansF(BASE):
    __tablename__ = "bans_feds"
    fed_id = Column(UnicodeText, primary_key=True)
    user_id = Column(String(14), primary_key=True)
    first_name = Column(UnicodeText, nullable=False)
    last_name = Column(UnicodeText)
    user_name = Column(UnicodeText)
    reason = Column(UnicodeText, default="")
    time = Column(Integer, default=0)

    def __init__(self, fed_id, user_id, first_name, last_name, user_name, reason, time):
        self.fed_id = fed_id
        self.user_id = user_id
        self.first_name = first_name
        self.last_name = last_name
        self.user_name = user_name
        self.reason = reason
        self.time = time


class FedsUserSettings(BASE):
    __tablename__ = "feds_settings"
    user_id = Column(Integer, primary_key=True)
    should_report = Column(Boolean, default=True)

    def __init__(self, user_id):
        self.user_id = user_id

    def __repr__(self):
        return "<Feds report settings ({})>".format(self.user_id)


class FedSubs(BASE):
    __tablename__ = "feds_subs"
    fed_id = Column(UnicodeText, primary_key=True)
    fed_subs = Column(UnicodeText, primary_key=True, nullable=False)

    def __init__(self, fed_id, fed_subs):
        self.fed_id = fed_id
        self.fed_subs = fed_subs

    def __repr__(self):
        return "<Fed {} subscribes for {}>".format(self.fed_id, self.fed_subs)


# Create tables if they don't exist
async def create_tables():
    async with async_session() as session:
        async with session.begin():
            await session.run_sync(BASE.metadata.create_all)


FEDS_LOCK = asyncio.Lock()
CHAT_FEDS_LOCK = asyncio.Lock()
FEDS_SETTINGS_LOCK = asyncio.Lock()
FEDS_SUBSCRIBER_LOCK = asyncio.Lock()

FEDERATION_BYNAME = {}
FEDERATION_BYOWNER = {}
FEDERATION_BYFEDID = {}

FEDERATION_CHATS = {}
FEDERATION_CHATS_BYID = {}

FEDERATION_BANNED_FULL = {}
FEDERATION_BANNED_USERID = {}

FEDERATION_NOTIFICATION = {}
FEDS_SUBSCRIBER = {}
MYFEDS_SUBSCRIBER = {}


async def get_fed_info(fed_id):
    get = FEDERATION_BYFEDID.get(str(fed_id))
    if get is None:
        return False
    return get


async def get_fed_id(chat_id):
    get = FEDERATION_CHATS.get(str(chat_id))
    if get is None:
        return False
    else:
        return get["fid"]


async def get_fed_name(chat_id):
    get = FEDERATION_CHATS.get(str(chat_id))
    if get is None:
        return False
    else:
        return get["chat_name"]


async def get_user_fban(fed_id, user_id):
    if not FEDERATION_BANNED_FULL.get(fed_id):
        return False, False, False
    user_info = FEDERATION_BANNED_FULL[fed_id].get(user_id)
    if not user_info:
        return None, None, None
    return user_info["first_name"], user_info["reason"], user_info["time"]


async def get_user_admin_fed_name(user_id):
    user_feds = []
    for f in FEDERATION_BYFEDID:
        if int(user_id) in ast.literal_eval(
            ast.literal_eval(FEDERATION_BYFEDID[f]["fusers"])["members"]
        ):
            user_feds.append(FEDERATION_BYFEDID[f]["fname"])
    return user_feds


async def get_user_owner_fed_name(user_id):
    user_feds = []
    for f in FEDERATION_BYFEDID:
        if int(user_id) == int(
            ast.literal_eval(FEDERATION_BYFEDID[f]["fusers"])["owner"]
        ):
            user_feds.append(FEDERATION_BYFEDID[f]["fname"])
    return user_feds


async def get_user_admin_fed_full(user_id):
    user_feds = []
    for f in FEDERATION_BYFEDID:
        if int(user_id) in ast.literal_eval(
            ast.literal_eval(FEDERATION_BYFEDID[f]["fusers"])["members"]
        ):
            user_feds.append({"fed_id": f, "fed": FEDERATION_BYFEDID[f]})
    return user_feds


async def get_user_owner_fed_full(user_id):
    user_feds = []
    for f in FEDERATION_BYFEDID:
        if int(user_id) == int(
            ast.literal_eval(FEDERATION_BYFEDID[f]["fusers"])["owner"]
        ):
            user_feds.append({"fed_id": f, "fed": FEDERATION_BYFEDID[f]})
    return user_feds


async def get_user_fbanlist(user_id):
    banlist = FEDERATION_BANNED_FULL
    user_name = ""
    fedname = []
    for x in banlist:
        if banlist[x].get(user_id):
            if user_name == "":
                user_name = banlist[x][user_id].get("first_name")
            fedname.append([x, banlist[x][user_id].get("reason")])
    return user_name, fedname


async def new_fed(owner_id, fed_name, fed_id):
    async with FEDS_LOCK:
        global FEDERATION_BYOWNER, FEDERATION_BYFEDID, FEDERATION_BYNAME
        fed = Federations(
            str(owner_id),
            fed_name,
            str(fed_id),
            "Rules is not set in this federation.",
            None,
            str({"owner": str(owner_id), "members": "[]"}),
        )
        async with async_session() as session:
            async with session.begin():
                session.add(fed)
                await session.commit()
        
        FEDERATION_BYOWNER[str(owner_id)] = {
            "fid": str(fed_id),
            "fname": fed_name,
            "frules": "Rules is not set in this federation.",
            "flog": None,
            "fusers": str({"owner": str(owner_id), "members": "[]"}),
        }
        FEDERATION_BYFEDID[str(fed_id)] = {
            "owner": str(owner_id),
            "fname": fed_name,
            "frules": "Rules is not set in this federation.",
            "flog": None,
            "fusers": str({"owner": str(owner_id), "members": "[]"}),
        }
        FEDERATION_BYNAME[fed_name] = {
            "fid": str(fed_id),
            "owner": str(owner_id),
            "frules": "Rules is not set in this federation.",
            "flog": None,
            "fusers": str({"owner": str(owner_id), "members": "[]"}),
        }
        return fed


async def del_fed(fed_id):
    async with FEDS_LOCK:
        global FEDERATION_BYOWNER, FEDERATION_BYFEDID, FEDERATION_BYNAME, FEDERATION_CHATS, FEDERATION_CHATS_BYID, FEDERATION_BANNED_USERID, FEDERATION_BANNED_FULL
        getcache = FEDERATION_BYFEDID.get(fed_id)
        if getcache is None:
            return False
        
        getfed = FEDERATION_BYFEDID.get(fed_id)
        owner_id = getfed["owner"]
        fed_name = getfed["fname"]
        
        FEDERATION_BYOWNER.pop(owner_id)
        FEDERATION_BYFEDID.pop(fed_id)
        FEDERATION_BYNAME.pop(fed_name)
        
        if FEDERATION_CHATS_BYID.get(fed_id):
            async with async_session() as session:
                for x in FEDERATION_CHATS_BYID[fed_id]:
                    delchats = await session.get(ChatF, str(x))
                    if delchats:
                        await session.delete(delchats)
                        await session.commit()
                    FEDERATION_CHATS.pop(x)
            FEDERATION_CHATS_BYID.pop(fed_id)
        
        getall = FEDERATION_BANNED_USERID.get(fed_id)
        if getall:
            async with async_session() as session:
                for x in getall:
                    banlist = await session.get(BansF, (fed_id, str(x)))
                    if banlist:
                        await session.delete(banlist)
                        await session.commit()
        
        if FEDERATION_BANNED_USERID.get(fed_id):
            FEDERATION_BANNED_USERID.pop(fed_id)
        if FEDERATION_BANNED_FULL.get(fed_id):
            FEDERATION_BANNED_FULL.pop(fed_id)
        
        getall = MYFEDS_SUBSCRIBER.get(fed_id)
        if getall:
            async with async_session() as session:
                for x in getall:
                    getsubs = await session.get(FedSubs, (fed_id, str(x)))
                    if getsubs:
                        await session.delete(getsubs)
                        await session.commit()
        
        if FEDS_SUBSCRIBER.get(fed_id):
            FEDS_SUBSCRIBER.pop(fed_id)
        if MYFEDS_SUBSCRIBER.get(fed_id):
            MYFEDS_SUBSCRIBER.pop(fed_id)
        
        async with async_session() as session:
            curr = await session.get(Federations, fed_id)
            if curr:
                await session.delete(curr)
                await session.commit()
        return True


async def rename_fed(fed_id, owner_id, newname):
    async with FEDS_LOCK:
        global FEDERATION_BYFEDID, FEDERATION_BYOWNER, FEDERATION_BYNAME
        async with async_session() as session:
            fed = await session.get(Federations, fed_id)
            if not fed:
                return False
            fed.fed_name = newname
            await session.commit()

        oldname = FEDERATION_BYFEDID[str(fed_id)]["fname"]
        tempdata = FEDERATION_BYNAME[oldname]
        FEDERATION_BYNAME.pop(oldname)

        FEDERATION_BYOWNER[str(owner_id)]["fname"] = newname
        FEDERATION_BYFEDID[str(fed_id)]["fname"] = newname
        FEDERATION_BYNAME[newname] = tempdata
        return True


async def chat_join_fed(fed_id, chat_name, chat_id):
    async with FEDS_LOCK:
        global FEDERATION_CHATS, FEDERATION_CHATS_BYID
        r = ChatF(chat_id, chat_name, fed_id)
        async with async_session() as session:
            async with session.begin():
                session.add(r)
                await session.commit()
        
        FEDERATION_CHATS[str(chat_id)] = {"chat_name": chat_name, "fid": fed_id}
        checkid = FEDERATION_CHATS_BYID.get(fed_id)
        if checkid is None:
            FEDERATION_CHATS_BYID[fed_id] = []
        FEDERATION_CHATS_BYID[fed_id].append(str(chat_id))
        return r


async def search_fed_by_name(fed_name):
    allfed = FEDERATION_BYNAME.get(fed_name)
    if allfed is None:
        return False
    return allfed


async def search_user_in_fed(fed_id, user_id):
    getfed = FEDERATION_BYFEDID.get(fed_id)
    if getfed is None:
        return False
    getfed = ast.literal_eval(getfed["fusers"])["members"]
    if user_id in ast.literal_eval(getfed):
        return True
    else:
        return False


async def user_demote_fed(fed_id, user_id):
    async with FEDS_LOCK:
        global FEDERATION_BYOWNER, FEDERATION_BYFEDID, FEDERATION_BYNAME
        getfed = FEDERATION_BYFEDID.get(str(fed_id))
        if not getfed:
            return False
            
        owner_id = getfed["owner"]
        fed_name = getfed["fname"]
        fed_rules = getfed["frules"]
        fed_log = getfed["flog"]
        
        try:
            members = ast.literal_eval(ast.literal_eval(getfed["fusers"])["members"])
        except ValueError:
            return False
            
        if user_id not in members:
            return False
            
        members.remove(user_id)
        
        FEDERATION_BYOWNER[str(owner_id)]["fusers"] = str(
            {"owner": str(owner_id), "members": str(members)},
        )
        FEDERATION_BYFEDID[str(fed_id)]["fusers"] = str(
            {"owner": str(owner_id), "members": str(members)},
        )
        FEDERATION_BYNAME[fed_name]["fusers"] = str(
            {"owner": str(owner_id), "members": str(members)},
        )
        
        fed = Federations(
            str(owner_id),
            fed_name,
            str(fed_id),
            fed_rules,
            fed_log,
            str({"owner": str(owner_id), "members": str(members)}),
        )
        
        async with async_session() as session:
            await session.merge(fed)
            await session.commit()
        
        return True


async def user_join_fed(fed_id, user_id):
    async with FEDS_LOCK:
        global FEDERATION_BYOWNER, FEDERATION_BYFEDID, FEDERATION_BYNAME
        getfed = FEDERATION_BYFEDID.get(str(fed_id))
        if not getfed:
            return False
            
        owner_id = getfed["owner"]
        fed_name = getfed["fname"]
        fed_rules = getfed["frules"]
        fed_log = getfed["flog"]
        
        members = ast.literal_eval(ast.literal_eval(getfed["fusers"])["members"])
        if user_id in members:
            return False
            
        members.append(user_id)
        
        FEDERATION_BYOWNER[str(owner_id)]["fusers"] = str(
            {"owner": str(owner_id), "members": str(members)},
        )
        FEDERATION_BYFEDID[str(fed_id)]["fusers"] = str(
            {"owner": str(owner_id), "members": str(members)},
        )
        FEDERATION_BYNAME[fed_name]["fusers"] = str(
            {"owner": str(owner_id), "members": str(members)},
        )
        
        fed = Federations(
            str(owner_id),
            fed_name,
            str(fed_id),
            fed_rules,
            fed_log,
            str({"owner": str(owner_id), "members": str(members)}),
        )
        
        async with async_session() as session:
            await session.merge(fed)
            await session.commit()
        
        await __load_all_feds_chats()
        return True


async def chat_leave_fed(chat_id):
    async with FEDS_LOCK:
        global FEDERATION_CHATS, FEDERATION_CHATS_BYID
        fed_info = FEDERATION_CHATS.get(str(chat_id))
        if fed_info is None:
            return False
            
        fed_id = fed_info["fid"]
        
        FEDERATION_CHATS.pop(str(chat_id))
        FEDERATION_CHATS_BYID[str(fed_id)].remove(str(chat_id))
        
        async with async_session() as session:
            stmt = delete(ChatF).where(ChatF.chat_id == str(chat_id))
            await session.execute(stmt)
            await session.commit()
        
        return True


async def all_fed_chats(fed_id):
    async with FEDS_LOCK:
        getfed = FEDERATION_CHATS_BYID.get(fed_id)
        if getfed is None:
            return []
        else:
            return getfed


async def all_fed_users(fed_id):
    async with FEDS_LOCK:
        getfed = FEDERATION_BYFEDID.get(str(fed_id))
        if getfed is None:
            return False
        fed_owner = ast.literal_eval(ast.literal_eval(getfed["fusers"])["owner"])
        fed_admins = ast.literal_eval(ast.literal_eval(getfed["fusers"])["members"])
        fed_admins.append(fed_owner)
        return fed_admins


async def all_fed_members(fed_id):
    async with FEDS_LOCK:
        getfed = FEDERATION_BYFEDID.get(str(fed_id))
        fed_admins = ast.literal_eval(ast.literal_eval(getfed["fusers"])["members"])
        return fed_admins


async def set_frules(fed_id, rules):
    async with FEDS_LOCK:
        global FEDERATION_BYOWNER, FEDERATION_BYFEDID, FEDERATION_BYNAME
        getfed = FEDERATION_BYFEDID.get(str(fed_id))
        if not getfed:
            return False
            
        owner_id = getfed["owner"]
        fed_name = getfed["fname"]
        fed_members = getfed["fusers"]
        fed_rules = str(rules)
        fed_log = getfed["flog"]
        
        FEDERATION_BYOWNER[str(owner_id)]["frules"] = fed_rules
        FEDERATION_BYFEDID[str(fed_id)]["frules"] = fed_rules
        FEDERATION_BYNAME[fed_name]["frules"] = fed_rules
        
        fed = Federations(
            str(owner_id),
            fed_name,
            str(fed_id),
            fed_rules,
            fed_log,
            str(fed_members),
        )
        
        async with async_session() as session:
            await session.merge(fed)
            await session.commit()
        
        return True


async def get_frules(fed_id):
    async with FEDS_LOCK:
        rules = FEDERATION_BYFEDID[str(fed_id)]["frules"]
        return rules


async def fban_user(fed_id, user_id, first_name, last_name, user_name, reason, time):
    async with FEDS_LOCK:
        async with async_session() as session:
            stmt = delete(BansF).where(
                (BansF.fed_id == str(fed_id)) & (BansF.user_id == str(user_id))
            )
            await session.execute(stmt)
            
            r = BansF(
                str(fed_id),
                str(user_id),
                first_name,
                last_name,
                user_name,
                reason,
                time,
            )
            
            session.add(r)
            try:
                await session.commit()
            except:
                await session.rollback()
                return False
            
            await __load_all_feds_banned()
            return r


async def multi_fban_user(
    multi_fed_id,
    multi_user_id,
    multi_first_name,
    multi_last_name,
    multi_user_name,
    multi_reason,
):
    async with FEDS_LOCK:
        counter = 0
        time = 0
        async with async_session() as session:
            for x in range(len(multi_fed_id)):
                fed_id = multi_fed_id[x]
                user_id = multi_user_id[x]
                first_name = multi_first_name[x]
                last_name = multi_last_name[x]
                user_name = multi_user_name[x]
                reason = multi_reason[x]
                
                stmt = delete(BansF).where(
                    (BansF.fed_id == str(fed_id)) & (BansF.user_id == str(user_id))
                )
                await session.execute(stmt)
                
                r = BansF(
                    str(fed_id),
                    str(user_id),
                    first_name,
                    last_name,
                    user_name,
                    reason,
                    time,
                )
                
                session.add(r)
                counter += 1
                
            try:
                await session.commit()
            except:
                await session.rollback()
                return False
            
            await __load_all_feds_banned()
            return counter


async def un_fban_user(fed_id, user_id):
    async with FEDS_LOCK:
        async with async_session() as session:
            stmt = delete(BansF).where(
                (BansF.fed_id == str(fed_id)) & (BansF.user_id == str(user_id))
            )
            result = await session.execute(stmt)
            await session.commit()
            
            if result.rowcount == 0:
                return False
                
            await __load_all_feds_banned()
            return True


async def get_fban_user(fed_id, user_id):
    list_fbanned = FEDERATION_BANNED_USERID.get(fed_id)
    if list_fbanned is None:
        FEDERATION_BANNED_USERID[fed_id] = []
    if user_id in FEDERATION_BANNED_USERID[fed_id]:
        async with async_session() as session:
            stmt = select(BansF).where(
                (BansF.fed_id == str(fed_id)) & (BansF.user_id == str(user_id))
            )
            result = await session.execute(stmt)
            ban = result.scalar_one_or_none()
            
            if ban:
                return True, ban.reason, ban.time
    return False, None, None


async def get_all_fban_users(fed_id):
    list_fbanned = FEDERATION_BANNED_USERID.get(fed_id)
    if list_fbanned is None:
        FEDERATION_BANNED_USERID[fed_id] = []
    return FEDERATION_BANNED_USERID[fed_id]


async def get_all_fban_users_target(fed_id, user_id):
    list_fbanned = FEDERATION_BANNED_FULL.get(fed_id)
    if list_fbanned is None:
        FEDERATION_BANNED_FULL[fed_id] = {}
        return False
    getuser = list_fbanned.get(str(user_id))
    return getuser


async def get_all_fban_users_global():
    list_fbanned = FEDERATION_BANNED_USERID
    total = []
    for x in list(FEDERATION_BANNED_USERID):
        for y in FEDERATION_BANNED_USERID[x]:
            total.append(y)
    return total


async def get_all_feds_users_global():
    list_fed = FEDERATION_BYFEDID
    total = []
    for x in list(FEDERATION_BYFEDID):
        total.append(FEDERATION_BYFEDID[x])
    return total


async def search_fed_by_id(fed_id):
    get = FEDERATION_BYFEDID.get(fed_id)
    if get is None:
        return False
    else:
        return get


async def user_feds_report(user_id: int) -> bool:
    user_setting = FEDERATION_NOTIFICATION.get(str(user_id))
    if user_setting is None:
        user_setting = True
    return user_setting


async def set_feds_setting(user_id: int, setting: bool):
    async with FEDS_SETTINGS_LOCK:
        global FEDERATION_NOTIFICATION
        async with async_session() as session:
            user_setting = await session.get(FedsUserSettings, user_id)
            if not user_setting:
                user_setting = FedsUserSettings(user_id)

            user_setting.should_report = setting
            FEDERATION_NOTIFICATION[str(user_id)] = setting
            session.add(user_setting)
            await session.commit()


async def get_fed_log(fed_id):
    fed_setting = FEDERATION_BYFEDID.get(str(fed_id))
    if fed_setting is None:
        fed_setting = False
        return fed_setting
    if fed_setting.get("flog") is None:
        return False
    elif fed_setting.get("flog"):
        try:
            from . import app
            await app.bot.get_chat(fed_setting.get("flog"))
        except BadRequest:
            await set_fed_log(fed_id, None)
            return False
        except TelegramError:
            await set_fed_log(fed_id, None)
            return False
        return fed_setting.get("flog")
    else:
        return False


async def set_fed_log(fed_id, chat_id):
    async with FEDS_LOCK:
        global FEDERATION_BYOWNER, FEDERATION_BYFEDID, FEDERATION_BYNAME
        getfed = FEDERATION_BYFEDID.get(str(fed_id))
        if not getfed:
            return False
            
        owner_id = getfed["owner"]
        fed_name = getfed["fname"]
        fed_members = getfed["fusers"]
        fed_rules = getfed["frules"]
        fed_log = str(chat_id)
        
        FEDERATION_BYOWNER[str(owner_id)]["flog"] = fed_log
        FEDERATION_BYFEDID[str(fed_id)]["flog"] = fed_log
        FEDERATION_BYNAME[fed_name]["flog"] = fed_log
        
        fed = Federations(
            str(owner_id),
            fed_name,
            str(fed_id),
            fed_rules,
            fed_log,
            str(fed_members),
        )
        
        async with async_session() as session:
            await session.merge(fed)
            await session.commit()
        
        return True


async def subs_fed(fed_id, my_fed):
    check = await get_spec_subs(fed_id, my_fed)
    if check:
        return False
        
    async with FEDS_SUBSCRIBER_LOCK:
        subsfed = FedSubs(fed_id, my_fed)
        
        async with async_session() as session:
            await session.merge(subsfed)
            await session.commit()
        
        global FEDS_SUBSCRIBER, MYFEDS_SUBSCRIBER
        if FEDS_SUBSCRIBER.get(fed_id, set()) == set():
            FEDS_SUBSCRIBER[fed_id] = {my_fed}
        else:
            FEDS_SUBSCRIBER.get(fed_id, set()).add(my_fed)
        
        if MYFEDS_SUBSCRIBER.get(my_fed, set()) == set():
            MYFEDS_SUBSCRIBER[my_fed] = {fed_id}
        else:
            MYFEDS_SUBSCRIBER.get(my_fed, set()).add(fed_id)
        
        return True


async def unsubs_fed(fed_id, my_fed):
    async with FEDS_SUBSCRIBER_LOCK:
        async with async_session() as session:
            getsubs = await session.get(FedSubs, (fed_id, my_fed))
            if getsubs:
                if my_fed in FEDS_SUBSCRIBER.get(fed_id, set()):
                    FEDS_SUBSCRIBER.get(fed_id, set()).remove(my_fed)
                if fed_id in MYFEDS_SUBSCRIBER.get(my_fed, set()):
                    MYFEDS_SUBSCRIBER.get(my_fed, set()).remove(fed_id)

                await session.delete(getsubs)
                await session.commit()
                return True

        return False


async def get_all_subs(fed_id):
    return FEDS_SUBSCRIBER.get(fed_id, set())


async def get_spec_subs(fed_id, fed_target):
    if FEDS_SUBSCRIBER.get(fed_id, set()) == set():
        return {}
    else:
        return FEDS_SUBSCRIBER.get(fed_id, fed_target)


async def get_mysubs(my_fed):
    return list(MYFEDS_SUBSCRIBER.get(my_fed, []))


async def get_subscriber(fed_id):
    return FEDS_SUBSCRIBER.get(fed_id, set())


async def __load_all_feds():
    global FEDERATION_BYOWNER, FEDERATION_BYFEDID, FEDERATION_BYNAME
    try:
        async with async_session() as session:
            result = await session.execute(select(Federations))
            feds = result.scalars().all()
            
            for x in feds:
                # Fed by Owner
                FEDERATION_BYOWNER[str(x.owner_id)] = {
                    "fid": str(x.fed_id),
                    "fname": x.fed_name,
                    "frules": x.fed_rules,
                    "flog": x.fed_log,
                    "fusers": str(x.fed_users),
                }
                # Fed By FedId
                FEDERATION_BYFEDID[str(x.fed_id)] = {
                    "owner": str(x.owner_id),
                    "fname": x.fed_name,
                    "frules": x.fed_rules,
                    "flog": x.fed_log,
                    "fusers": str(x.fed_users),
                }
                # Fed By Name
                FEDERATION_BYNAME[x.fed_name] = {
                    "fid": str(x.fed_id),
                    "owner": str(x.owner_id),
                    "frules": x.fed_rules,
                    "flog": x.fed_log,
                    "fusers": str(x.fed_users),
                }
    except Exception as e:
        print(f"Error loading feds: {e}")


async def __load_all_feds_chats():
    global FEDERATION_CHATS, FEDERATION_CHATS_BYID
    try:
        async with async_session() as session:
            result = await session.execute(select(ChatF))
            qall = result.scalars().all()
            
            FEDERATION_CHATS = {}
            FEDERATION_CHATS_BYID = {}
            
            for x in qall:
                FEDERATION_CHATS[x.chat_id] = {"chat_name": x.chat_name, "fid": x.fed_id}
                
                if FEDERATION_CHATS_BYID.get(x.fed_id) is None:
                    FEDERATION_CHATS_BYID[x.fed_id] = []
                FEDERATION_CHATS_BYID[x.fed_id].append(x.chat_id)
    except Exception as e:
        print(f"Error loading fed chats: {e}")


async def __load_all_feds_banned():
    global FEDERATION_BANNED_USERID, FEDERATION_BANNED_FULL
    try:
        async with async_session() as session:
            result = await session.execute(select(BansF))
            qall = result.scalars().all()
            
            FEDERATION_BANNED_USERID = {}
            FEDERATION_BANNED_FULL = {}
            
            for x in qall:
                if FEDERATION_BANNED_USERID.get(x.fed_id) is None:
                    FEDERATION_BANNED_USERID[x.fed_id] = []
                if int(x.user_id) not in FEDERATION_BANNED_USERID[x.fed_id]:
                    FEDERATION_BANNED_USERID[x.fed_id].append(int(x.user_id))
                
                if FEDERATION_BANNED_FULL.get(x.fed_id) is None:
                    FEDERATION_BANNED_FULL[x.fed_id] = {}
                FEDERATION_BANNED_FULL[x.fed_id][x.user_id] = {
                    "first_name": x.first_name,
                    "last_name": x.last_name,
                    "user_name": x.user_name,
                    "reason": x.reason,
                    "time": x.time,
                }
    except Exception as e:
        print(f"Error loading fed bans: {e}")


async def __load_all_feds_settings():
    global FEDERATION_NOTIFICATION
    try:
        async with async_session() as session:
            result = await session.execute(select(FedsUserSettings))
            getuser = result.scalars().all()
            
            for x in getuser:
                FEDERATION_NOTIFICATION[str(x.user_id)] = x.should_report
    except Exception as e:
        print(f"Error loading fed settings: {e}")


async def __load_feds_subscriber():
    global FEDS_SUBSCRIBER, MYFEDS_SUBSCRIBER
    try:
        async with async_session() as session:
            # Get distinct fed_ids
            result = await session.execute(select(FedSubs.fed_id).distinct())
            feds = result.scalars().all()
            
            FEDS_SUBSCRIBER = {fed_id: set() for fed_id in feds}
            MYFEDS_SUBSCRIBER = {}
            
            # Get all subscriptions
            result = await session.execute(select(FedSubs))
            all_fedsubs = result.scalars().all()
            
            for x in all_fedsubs:
                FEDS_SUBSCRIBER[x.fed_id].add(x.fed_subs)
                
                if MYFEDS_SUBSCRIBER.get(x.fed_subs) is None:
                    MYFEDS_SUBSCRIBER[x.fed_subs] = set()
                MYFEDS_SUBSCRIBER[x.fed_subs].add(x.fed_id)
                
    except Exception as e:
        print(f"Error loading fed subscribers: {e}")


async def load_all():
    await __load_all_feds()
    await __load_all_feds_chats()
    await __load_all_feds_banned()
    await __load_all_feds_settings()
    await __load_feds_subscriber()


# Initialize on startup
async def initialize():
    await create_tables()
    await load_all()


# Run the initialization
asyncio.create_task(initialize())
