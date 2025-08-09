import random
from typing import Union

from Hina.modules.helper_funcs.msg_types import Types
from .db_connection import BASE, async_session, session_scope
from sqlalchemy import BigInteger, Boolean, Column, Integer, String, UnicodeText
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete

DEFAULT_WELCOME = "Hey {first}, how are you?"
DEFAULT_GOODBYE = "Nice knowing ya!"

DEFAULT_WELCOME_MESSAGES = [
    "{first} is here!",  # Discord welcome messages copied
    "Ready player {first}",
    "Genos, {first} is here.",
    "A wild {first} appeared.",
    "{first} came in like a Lion!",
    "{first} has joined your party.",
    "{first} just joined. Can I get a heal?",
    "{first} just joined the chat - asdgfhak!",
    "{first} just joined. Everyone, look busy!",
    "Welcome, {first}. Stay awhile and listen.",
    "Welcome, {first}. We were expecting you ( ͡° ͜ʖ ͡°)",
    "Welcome, {first}. We hope you brought pizza.",
    "Welcome, {first}. Leave your weapons by the door.",
    "Swoooosh. {first} just landed.",
    "Brace yourselves. {first} just joined the chat.",
    "{first} just joined. Hide your bananas.",
    "{first} just arrived. Seems OP - please nerf.",
    "{first} just slid into the chat.",
    "A {first} has spawned in the chat.",
    "Big {first} showed up!",
    "Where's {first}? In the chat!",
    "{first} hopped into the chat. Kangaroo!!",
    "{first} just showed up. Hold my beer.",
    "Challenger approaching! {first} has appeared!",
    "It's a bird! It's a plane! Nevermind, it's just {first}.",
    "It's {first}! Praise the sun! \o/",
    "Never gonna give {first} up. Never gonna let {first} down.",
    "Ha! {first} has joined! You activated my trap card!",
    "Hey! Listen! {first} has joined!",
    "We've been expecting you {first}",
    "It's dangerous to go alone, take {first}!",
    "{first} has joined the chat! It's super effective!",
    "Cheers, love! {first} is here!",
    "{first} is here, as the prophecy foretold.",
    "{first} has arrived. Party's over.",
    "{first} is here to kick butt and chew bubblegum. And {first} is all out of gum.",
    "Hello. Is it {first} you're looking for?",
    "{first} has joined. Stay awhile and listen!",
    "Roses are red, violets are blue, {first} joined this chat with you",
    "Welcome {first}, Avoid Punches if you can!",
    "It's a bird! It's a plane! - Nope, its {first}!",
    "{first} Joined! - Ok.",  # Discord welcome messages end.
    "All Hail {first}!",
    "Hi, {first}. Don't lurk, only Villans do that.",
    "{first} has joined the battle bus.",
    "A new Challenger enters!",  # Tekken
    "Ok!",
    "{first} just fell into the chat!",
    "Something just fell from the sky! - oh, its {first}.",
    "{first} Just teleported into the chat!",
    "Hi, {first}, show me your Hunter License!",  # Hunter Hunter
    "I'm looking for Garo, oh wait nvm it's {first}.",  # One Punch man s2
    "Welcome {first}, leaving is not an option!",
    "Run Forest! ..I mean...{first}.",
    "{first} do 100 push-ups, 100 sit-ups, 100 squats, and 10km running EVERY SINGLE DAY!!!",  # One Punch ma
    "Huh?\nDid someone with a disaster level just join?\nOh wait, it's just {first}.",  # One Punch ma
    "Hey, {first}, ever heard the King Engine?",  # One Punch ma
    "Hey, {first}, empty your pockets.",
    "Hey, {first}!, are you strong?",
    "Call the Avengers! - {first} just joined the chat.",
    "{first} joined. You must construct additional pylons.",
    "Ermagherd. {first} is here.",
    "Come for the Snail Racing, Stay for the Chimichangas!",
    "Who needs Google? You're everything we were searching for.",
    "This place must have free WiFi, cause I'm feeling a connection.",
    "Speak friend and enter.",
    "Welcome you are",
    "Welcome {first}, your princess is in another castle.",
    "Hi {first}, welcome to the dark side.",
    "Hola {first}, beware of people with disaster levels",
    "Hey {first}, we have the droids you are looking for.",
    "Hi {first}\nThis isn't a strange place, this is my home, it's the people who are strange.",
    "Oh, hey {first} what's the password?",
    "Hey {first}, I know what we're gonna do today",
    "{first} just joined, be at alert they could be a spy.",
    "{first} joined the group, read by Mark Zuckerberg, CIA and 35 others.",
    "Welcome {first}, watch out for falling monkeys.",
    "Everyone stop what you're doing, We are now in the presence of {first}.",
    "Hey {first}, do you wanna know how I got these scars?",
    "Welcome {first}, drop your weapons and proceed to the spy scanner.",
    "Stay safe {first}, Keep 3 meters social distances between your messages.",  # Corona memes lmao
    "Hey {first}, Do you know I once One-punched a meteorite?",
    "You're here now {first}, Resistance is futile",
    "{first} just arrived, the force is strong with this one.",
    "{first} just joined on president's orders.",
    "Hi {first}, is the glass half full or half empty?",
    "Yipee Kayaye {first} arrived.",
    "Welcome {first}, if you're a secret agent press 1, otherwise start a conversation",
    "{first}, I have a feeling we're not in Kansas anymore.",
    "They may take our lives, but they'll never take our {first}.",
    "Coast is clear! You can come out guys, it's just {first}.",
    "Welcome {first}, pay no attention to that guy lurking.",
    "Welcome {first}, may the force be with you.",
    "May the {first} be with you.",
    "{first} just joined. Hey, where's Perry?",
    "{first} just joined. Oh, there you are, Perry.",
    "Ladies and gentlemen, I give you ...  {first}.",
    "Behold my new evil scheme, the {first}-Inator.",
    "Ah, {first} the Platypus, you're just in time... to be trapped.",
    "{first} just arrived. Diable Jamble!",  # One Piece Sanji
    "{first} just arrived. Aschente!",  # No Game No Life
    "{first} say Aschente to swear by the pledges.",  # No Game No Life
    "{first} just joined. El Psy congroo!",  # Steins Gate
    "Irasshaimase {first}!",  # weeabo shit
    "Hi {first}, what is 1000-7?",  # tokyo ghoul
    "Come. I don't want to destroy this place",  # hunter x hunter
    "I... am... Whitebeard!...wait..wrong anime.",  # one Piece
    "Hey {first}...have you ever heard these words?",  # BNHA
    "Can't a guy get a little sleep around here?",  # Kamina Falls - Gurren Lagann
    "It's time someone put you in your place, {first}.",  # Hellsing
    "Unit-01's reactivated..",  # Neon Genesis: Evangelion
    "Prepare for trouble...And make it double",  # Pokemon
    "Hey {first}, are You Challenging Me?",  # Shaggy
    "Oh? You're Approaching Me?",  # jojo
    "Ho... mukatta kuruno ka?",  # jojo jap ver
    "I can't beat the shit out of you without getting closer",  # jojo
    "Ho ho! Then come as close as you'd like.",  # jojo
    "Hoho! Dewa juubun chikazukanai youi",  # jojo jap ver
    "Guess who survived his time in Hell, {first}.",  # jojo
    "How many loaves of bread have you eaten in your lifetime?",  # jojo
    "What did you say? Depending on your answer, I may have to kick your ass!",  # jojo
    "Oh? You're approaching me? Instead of running away, you come right to me? Even though your grandfather, Joseph, told you the secret of The World, like an exam student scrambling to finish the problems on an exam until the last moments before the chime?",  # jojo
    "Rerorerorerorerorero.",  # jojo
    "{first} just warped into the group!",
    "I..it's..it's just {first}.",
    "Sugoi, Dekai. {first} Joined!",
    "{first}, do you know gods of death love apples?",  # Death Note owo
    "I'll take a potato chip.... and eat it",  # Death Note owo
    "Oshiete oshiete yo sono shikumi wo!",  # Tokyo Ghoul
    "Kaizoku ou ni...nvm wrong anime.",  # op
    "{first} just joined! Gear.....second!",  # Op
    "Omae wa mou....shindeiru",
    "Hey {first}, the leaf village lotus blooms twice!",  # Naruto stuff begins from here
    "{first} Joined! Omote renge!",
    "{first}! I, Madara! declare you the strongest",
    "{first}, this time I'll lend you my power. ",  # Kyuubi to naruto
    "{first}, welcome to the hidden leaf village!",  # Naruto thingies end here
    "In the jungle, you must wait...until the dice read five or eight.",  # Jumanji stuff
    "Dr.{first} Famed archeologist and international explorer,\nWelcome to Jumanji!\nJumanji's Fate is up to you now.",
    "{first}, this will not be an easy mission - monkeys slow the expedition.",  # End of Jumanji stuff
    "Remember, remember, the Fifth of November, the Gunpowder Treason and Plot. I know of no reason why the Gunpowder Treason should ever be forgot.",  # V for Vendetta
    "The only verdict is vengeance; a vendetta, held as a votive not in vain, for the value and veracity of such shall one day vindicate the vigilant and the virtuous.",  # V for Vendetta
    "Behind {first} there is more than just flesh. Beneath this user there is an idea... and ideas are bulletproof.",  # V for Vendetta
    "Love your rage, not your cage.",  # V for Vendetta
    "Get your stinking paws off me, you damned dirty ape!",  # Planet of the apes
    "Elementary, my dear {first}.",
    "I'm back - {first}.",
    "Bond. {first} Bond.",
    "Come with me if you want to live",
]
DEFAULT_GOODBYE_MESSAGES = [
    "{first} will be missed.",
    "{first} just went offline.",
    "{first} has left the lobby.",
    "{first} has left the clan.",
    "{first} has left the game.",
    "{first} has fled the area.",
    "{first} is out of the running.",
    "Nice knowing ya, {first}!",
    "It was a fun time {first}.",
    "We hope to see you again soon, {first}.",
    "I donut want to say goodbye, {first}.",
    "Goodbye {first}! Guess who's gonna miss you :')",
    "Goodbye {first}! It's gonna be lonely without ya.",
    "Please don't leave me alone in this place, {first}!",
    "Good luck finding better shit-posters than us, {first}!",
    "You know we're gonna miss you {first}. Right? Right? Right?",
    "Congratulations, {first}! You're officially free of this mess.",
    "{first}. You were an opponent worth fighting.",
    "You're leaving, {first}? Yare Yare Daze.",
    "Bring him the photo",
    "Go outside!",
    "Ask again later",
    "Think for yourself",
    "Question authority",
    "You are worshiping a sun god",
    "Don't leave the house today",
    "Give up!",
    "Marry and reproduce",
    "Stay asleep",
    "Wake up",
    "Look to la luna",
    "Steven lives",
    "Meet strangers without prejudice",
    "A hanged man will bring you no luck today",
    "What do you want to do today?",
    "You are dark inside",
    "Have you seen the exit?",
    "Get a baby pet it will cheer you up.",
    "Your princess is in another castle.",
    "You are playing it wrong give me the controller",
    "Trust good people",
    "Live to die.",
    "When life gives you lemons reroll!",
    "Well, that was worthless",
    "I fell asleep!",
    "May your troubles be many",
    "Your old life lies in ruin",
    "Always look on the bright side",
    "It is dangerous to go alone",
    "You will never be forgiven",
    "You have nobody to blame but yourself",
    "Only a sinner",
    "Use bombs wisely",
    "Nobody knows the troubles you have seen",
    "You look fat you should exercise more",
    "Follow the zebra",
    "Why so blue?",
    "The devil in disguise",
    "Go outside",
    "Always your head in the clouds",
]


# [Keep all the DEFAULT_WELCOME_MESSAGES and DEFAULT_GOODBYE_MESSAGES lists unchanged...]

class Welcome(BASE):
    __tablename__ = "welcome_pref"
    chat_id = Column(String(14), primary_key=True)
    should_welcome = Column(Boolean, default=True)
    should_goodbye = Column(Boolean, default=True)
    custom_content = Column(UnicodeText, default=None)

    custom_welcome = Column(
        UnicodeText,
        default=random.choice(DEFAULT_WELCOME_MESSAGES),
    )
    welcome_type = Column(Integer, default=Types.TEXT.value)

    custom_leave = Column(UnicodeText, default=random.choice(DEFAULT_GOODBYE_MESSAGES))
    leave_type = Column(Integer, default=Types.TEXT.value)

    clean_welcome = Column(BigInteger)

    def __init__(self, chat_id, should_welcome=True, should_goodbye=True):
        self.chat_id = chat_id
        self.should_welcome = should_welcome
        self.should_goodbye = should_goodbye

    def __repr__(self):
        return f"<Chat {self.chat_id} should Welcome new users: {self.should_welcome}>"

# [Keep all the other model classes unchanged...]

async def welcome_mutes(chat_id):
    async with AsyncSession(async_session().bind) as session:
        result = await session.execute(select(WelcomeMute).where(WelcomeMute.chat_id == str(chat_id)))
        welcomemutes = result.scalars().first()
        if welcomemutes:
            return welcomemutes.welcomemutes
        return False

async def set_welcome_mutes(chat_id, welcomemutes):
    async with AsyncSession(async_session().bind) as session:
        async with session.begin():
            result = await session.execute(select(WelcomeMute).where(WelcomeMute.chat_id == str(chat_id)))
            prev = result.scalars().first()
            if prev:
                await session.delete(prev)
            
            welcome_m = WelcomeMute(str(chat_id), welcomemutes)
            session.add(welcome_m)
            await session.commit()

async def set_human_checks(user_id, chat_id):
    async with AsyncSession(async_session().bind) as session:
        async with session.begin():
            result = await session.execute(
                select(WelcomeMuteUsers)
                .where(WelcomeMuteUsers.user_id == user_id)
                .where(WelcomeMuteUsers.chat_id == str(chat_id))
            )
            human_check = result.scalars().first()
            
            if not human_check:
                human_check = WelcomeMuteUsers(user_id, str(chat_id), True)
            else:
                human_check.human_check = True

            session.add(human_check)
            await session.commit()
            return human_check

async def get_human_checks(user_id, chat_id):
    async with AsyncSession(async_session().bind) as session:
        result = await session.execute(
            select(WelcomeMuteUsers)
            .where(WelcomeMuteUsers.user_id == user_id)
            .where(WelcomeMuteUsers.chat_id == str(chat_id))
        )
        human_check = result.scalars().first()
        if not human_check:
            return None
        return human_check.human_check

async def get_welc_mutes_pref(chat_id):
    async with AsyncSession(async_session().bind) as session:
        result = await session.execute(select(WelcomeMute).where(WelcomeMute.chat_id == str(chat_id)))
        welcomemutes = result.scalars().first()
        if welcomemutes:
            return welcomemutes.welcomemutes
        return False

async def get_welc_pref(chat_id):
    async with AsyncSession(async_session().bind) as session:
        result = await session.execute(select(Welcome).where(Welcome.chat_id == str(chat_id)))
        welc = result.scalars().first()
        if welc:
            return (
                welc.should_welcome,
                welc.custom_welcome,
                welc.custom_content,
                welc.welcome_type,
            )
        return True, DEFAULT_WELCOME, None, Types.TEXT

async def get_gdbye_pref(chat_id):
    async with AsyncSession(async_session().bind) as session:
        result = await session.execute(select(Welcome).where(Welcome.chat_id == str(chat_id)))
        welc = result.scalars().first()
        if welc:
            return welc.should_goodbye, welc.custom_leave, welc.leave_type
        return True, DEFAULT_GOODBYE, Types.TEXT

async def set_clean_welcome(chat_id, clean_welcome):
    async with AsyncSession(async_session().bind) as session:
        async with session.begin():
            result = await session.execute(select(Welcome).where(Welcome.chat_id == str(chat_id)))
            curr = result.scalars().first()
            if not curr:
                curr = Welcome(str(chat_id))
            
            curr.clean_welcome = int(clean_welcome)
            session.add(curr)
            await session.commit()

async def get_clean_pref(chat_id):
    async with AsyncSession(async_session().bind) as session:
        result = await session.execute(select(Welcome).where(Welcome.chat_id == str(chat_id)))
        welc = result.scalars().first()
        if welc:
            return welc.clean_welcome
        return False

async def set_welc_preference(chat_id, should_welcome):
    async with AsyncSession(async_session().bind) as session:
        async with session.begin():
            result = await session.execute(select(Welcome).where(Welcome.chat_id == str(chat_id)))
            curr = result.scalars().first()
            if not curr:
                curr = Welcome(str(chat_id), should_welcome=should_welcome)
            else:
                curr.should_welcome = should_welcome

            session.add(curr)
            await session.commit()

async def set_gdbye_preference(chat_id, should_goodbye):
    async with AsyncSession(async_session().bind) as session:
        async with session.begin():
            result = await session.execute(select(Welcome).where(Welcome.chat_id == str(chat_id)))
            curr = result.scalars().first()
            if not curr:
                curr = Welcome(str(chat_id), should_goodbye=should_goodbye)
            else:
                curr.should_goodbye = should_goodbye

            session.add(curr)
            await session.commit()

async def set_custom_welcome(
    chat_id,
    custom_content,
    custom_welcome,
    welcome_type,
    buttons=None,
):
    if buttons is None:
        buttons = []

    async with AsyncSession(async_session().bind) as session:
        async with session.begin():
            result = await session.execute(select(Welcome).where(Welcome.chat_id == str(chat_id)))
            welcome_settings = result.scalars().first()
            if not welcome_settings:
                welcome_settings = Welcome(str(chat_id), True)

            if custom_welcome or custom_content:
                welcome_settings.custom_content = custom_content
                welcome_settings.custom_welcome = custom_welcome
                welcome_settings.welcome_type = welcome_type.value
            else:
                welcome_settings.custom_welcome = DEFAULT_WELCOME
                welcome_settings.welcome_type = Types.TEXT.value

            session.add(welcome_settings)

            # Delete previous buttons
            await session.execute(delete(WelcomeButtons).where(WelcomeButtons.chat_id == str(chat_id)))
            
            # Add new buttons
            for b_name, url, same_line in buttons:
                button = WelcomeButtons(chat_id, b_name, url, same_line)
                session.add(button)

            await session.commit()

async def get_custom_welcome(chat_id):
    async with AsyncSession(async_session().bind) as session:
        result = await session.execute(select(Welcome).where(Welcome.chat_id == str(chat_id)))
        welcome_settings = result.scalars().first()
        if welcome_settings and welcome_settings.custom_welcome:
            return welcome_settings.custom_welcome
        return DEFAULT_WELCOME

async def set_custom_gdbye(chat_id, custom_goodbye, goodbye_type, buttons=None):
    if buttons is None:
        buttons = []

    async with AsyncSession(async_session().bind) as session:
        async with session.begin():
            result = await session.execute(select(Welcome).where(Welcome.chat_id == str(chat_id)))
            welcome_settings = result.scalars().first()
            if not welcome_settings:
                welcome_settings = Welcome(str(chat_id), True)

            if custom_goodbye:
                welcome_settings.custom_leave = custom_goodbye
                welcome_settings.leave_type = goodbye_type.value
            else:
                welcome_settings.custom_leave = DEFAULT_GOODBYE
                welcome_settings.leave_type = Types.TEXT.value

            session.add(welcome_settings)

            # Delete previous buttons
            await session.execute(delete(GoodbyeButtons).where(GoodbyeButtons.chat_id == str(chat_id)))
            
            # Add new buttons
            for b_name, url, same_line in buttons:
                button = GoodbyeButtons(chat_id, b_name, url, same_line)
                session.add(button)

            await session.commit()

async def get_custom_gdbye(chat_id):
    async with AsyncSession(async_session().bind) as session:
        result = await session.execute(select(Welcome).where(Welcome.chat_id == str(chat_id)))
        welcome_settings = result.scalars().first()
        if welcome_settings and welcome_settings.custom_leave:
            return welcome_settings.custom_leave
        return DEFAULT_GOODBYE

async def get_welc_buttons(chat_id):
    async with AsyncSession(async_session().bind) as session:
        result = await session.execute(
            select(WelcomeButtons)
            .where(WelcomeButtons.chat_id == str(chat_id))
            .order_by(WelcomeButtons.id)
        )
        return result.scalars().all()

async def get_gdbye_buttons(chat_id):
    async with AsyncSession(async_session().bind) as session:
        result = await session.execute(
            select(GoodbyeButtons)
            .where(GoodbyeButtons.chat_id == str(chat_id))
            .order_by(GoodbyeButtons.id)
        )
        return result.scalars().all()

async def clean_service(chat_id: Union[str, int]) -> bool:
    async with AsyncSession(async_session().bind) as session:
        result = await session.execute(select(CleanServiceSetting).where(CleanServiceSetting.chat_id == str(chat_id)))
        chat_setting = result.scalars().first()
        if chat_setting:
            return chat_setting.clean_service
        return False

async def set_clean_service(chat_id: Union[int, str], setting: bool):
    async with AsyncSession(async_session().bind) as session:
        async with session.begin():
            result = await session.execute(select(CleanServiceSetting).where(CleanServiceSetting.chat_id == str(chat_id)))
            chat_setting = result.scalars().first()
            if not chat_setting:
                chat_setting = CleanServiceSetting(chat_id)

            chat_setting.clean_service = setting
            session.add(chat_setting)
            await session.commit()

async def migrate_chat(old_chat_id, new_chat_id):
    async with AsyncSession(async_session().bind) as session:
        async with session.begin():
            # Update Welcome
            result = await session.execute(select(Welcome).where(Welcome.chat_id == str(old_chat_id)))
            chat = result.scalars().first()
            if chat:
                chat.chat_id = str(new_chat_id)
                session.add(chat)

            # Update WelcomeButtons
            await session.execute(
                update(WelcomeButtons)
                .where(WelcomeButtons.chat_id == str(old_chat_id))
                .values(chat_id=str(new_chat_id))
            )

            # Update GoodbyeButtons
            await session.execute(
                update(GoodbyeButtons)
                .where(GoodbyeButtons.chat_id == str(old_chat_id))
                .values(chat_id=str(new_chat_id))
            )

            await session.commit()
