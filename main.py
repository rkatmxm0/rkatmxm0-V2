import discord
from discord.ext import commands
from discord import app_commands
import json, os, secrets, string
from datetime import datetime

# ─────────────────────────────────────────
#  설정값 — 여기만 수정하세요
# ─────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DEVELOPER_ID   = 1238831881110290444
CHARGE_CH_ID   = 1492515053755437157   # ← 충전 요청 알림 받을 채널 ID (직접 입력)
BANK_NAME      = "토스뱅크"
BANK_ACCOUNT   = "1908-5337-3454"
BANK_HOLDER    = "이영훈"
BOT_COLOR      = 0x5865F2
SUCCESS_COLOR  = 0x57F287
ERROR_COLOR    = 0xED4245
WARN_COLOR     = 0xFEE75C
GOLD_COLOR     = 0xF1C40F
# ─────────────────────────────────────────

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# ─────────────────────────────────────────
#  서버별 데이터 저장/불러오기
# ─────────────────────────────────────────
def guild_dir(guild_id) -> str:
    path = f"{DATA_DIR}/{guild_id}"
    os.makedirs(path, exist_ok=True)
    return path

def load_guild(guild_id, filename: str) -> dict:
    path = f"{guild_dir(guild_id)}/{filename}"
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_guild(guild_id, filename: str, data):
    with open(f"{guild_dir(guild_id)}/{filename}", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load(filename: str) -> dict:
    path = f"{DATA_DIR}/{filename}"
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save(filename: str, data):
    with open(f"{DATA_DIR}/{filename}", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────
#  라이센스 헬퍼
# ─────────────────────────────────────────
def generate_license_key() -> str:
    chars = string.ascii_uppercase + string.digits
    return '-'.join(''.join(secrets.choice(chars) for _ in range(4)) for _ in range(4))

def get_guild_license(guild_id) -> dict:
    return load("licenses.json").get(str(guild_id), {})

def is_licensed_user(guild_id, user_id: int) -> bool:
    guild_lic = get_guild_license(guild_id)
    if not guild_lic.get("active", False):
        return False
    for u in guild_lic.get("users", []):
        if u["user_id"] == user_id and not u.get("suspended", False):
            return True
    return False

# ─────────────────────────────────────────
#  공통 임베드 헬퍼
# ─────────────────────────────────────────
def base_embed(title, desc="", color=BOT_COLOR):
    e = discord.Embed(title=title, description=desc, color=color)
    e.timestamp = datetime.utcnow()
    e.set_footer(text="rkatmxm0 V2 · 관리자 승인 시스템")
    return e

def license_required_embed():
    e = discord.Embed(
        title="🔒  라이센스 필요",
        description="이 명령어를 사용하려면 라이센스가 필요해요.\n`/라이센스등록` 명령어로 라이센스를 등록해 주세요.",
        color=ERROR_COLOR
    )
    e.set_footer(text="rkatmxm0 V2 · 라이센스 시스템")
    e.timestamp = datetime.utcnow()
    return e

def no_permission_embed():
    e = discord.Embed(
        title="🚫  권한 없음",
        description="개발자만 사용할 수 있어요.",
        color=ERROR_COLOR
    )
    e.set_footer(text="rkatmxm0 V2 · 라이센스 시스템")
    e.timestamp = datetime.utcnow()
    return e

# ─────────────────────────────────────────
#  충전 Modal
# ─────────────────────────────────────────
class ChargeModal(discord.ui.Modal, title="💳 충전 신청"):
    amount      = discord.ui.TextInput(label="충전 금액 (원)", placeholder="예: 10000", min_length=1, max_length=10)
    sender_name = discord.ui.TextInput(label="입금자명", placeholder="통장에 표시될 이름 그대로 입력", min_length=1, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            gid = interaction.guild_id
            uid = str(interaction.user.id)
            users = load_guild(gid, "users.json")

            if users.get(uid, {}).get("pending_charge"):
                await interaction.response.send_message(embed=base_embed(
                    "⏳ 대기 중인 요청 있음",
                    "이미 충전 요청이 처리 중이에요.\n관리자가 승인 또는 거절할 때까지 기다려 주세요.", WARN_COLOR
                ), ephemeral=True)
                return

            try:
                amt = int(self.amount.value.replace(",", "").replace(" ", "").replace("원", ""))
                if amt <= 0:
                    raise ValueError
            except ValueError:
                await interaction.response.send_message(
                    embed=base_embed("❌ 잘못된 금액", "숫자만 입력해 주세요. (예: 10000)", ERROR_COLOR),
                    ephemeral=True
                )
                return

            if uid not in users:
                users[uid] = {"balance": 0, "purchases": [], "pending_charge": False}
            users[uid]["pending_charge"] = True
            save_guild(gid, "users.json", users)

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 유저에게 확인 임베드
            ue = base_embed("📨 충전 신청 완료", "아래 계좌로 **정확히** 입금해 주세요.\n관리자 승인 후 잔액이 추가됩니다.", BOT_COLOR)
            ue.add_field(name="🏦 은행",      value=f"`{BANK_NAME}`",    inline=True)
            ue.add_field(name="💳 계좌번호",  value=f"`{BANK_ACCOUNT}`", inline=True)
            ue.add_field(name="👤 예금주",    value=f"`{BANK_HOLDER}`",  inline=True)
            ue.add_field(name="💰 입금 금액", value=f"**{amt:,}원**",    inline=True)
            ue.add_field(name="✍️ 입금자명",  value=f"`{self.sender_name.value}`", inline=True)
            ue.add_field(name="🕐 신청 시각", value=f"`{now_str}`",      inline=True)
            ue.add_field(name="⚠️ 주의사항",
                value="• 입금자명이 다르면 처리가 지연될 수 있어요\n• 승인 전까지 중복 신청은 불가해요\n• 입금 후 잠시 기다려 주세요", inline=False)
            ue.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/2489/2489756.png")
            await interaction.response.send_message(embed=ue, ephemeral=True)

            # 관리자 채널에 전송 (설정값의 고정 채널 ID 사용)
            charge_ch = bot.get_channel(CHARGE_CH_ID)
            if not charge_ch:
                return

            ae = base_embed("🔔 신규 충전 요청", f"{interaction.user.mention} 님이 충전을 신청했습니다.", WARN_COLOR)
            ae.add_field(name="👤 닉네임",    value=f"`{interaction.user.display_name}`", inline=True)
            ae.add_field(name="🆔 유저 ID",   value=f"`{interaction.user.id}`",           inline=True)
            ae.add_field(name="✍️ 입금자명",  value=f"`{self.sender_name.value}`",        inline=True)
            ae.add_field(name="💰 신청 금액", value=f"**{amt:,}원**",                     inline=True)
            ae.add_field(name="🏦 계좌",      value=f"`{BANK_ACCOUNT}`",                  inline=True)
            ae.add_field(name="🕐 신청 시각", value=f"`{now_str}`",                       inline=True)
            ae.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
            ae.set_footer(text="아래 버튼으로 승인 또는 거절하세요")
            await charge_ch.send(embed=ae, view=ChargeApproveView(interaction.user.id, amt, self.sender_name.value, gid))

        except Exception as e:
            print(f"[ChargeModal 에러] {e}")
            try:
                await interaction.response.send_message(
                    embed=base_embed("❌ 오류 발생", f"처리 중 오류가 발생했어요.\n잠시 후 다시 시도해 주세요.\n`{e}`", ERROR_COLOR),
                    ephemeral=True
                )
            except:
                pass


# ─────────────────────────────────────────
#  충전 승인/거절 버튼
# ─────────────────────────────────────────
class ChargeApproveView(discord.ui.View):
    def __init__(self, user_id: int, amount: int, sender: str, guild_id):
        super().__init__(timeout=None)
        self.user_id  = user_id
        self.amount   = amount
        self.sender   = sender
        self.guild_id = guild_id

    async def _check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == DEVELOPER_ID:
            return True
        if is_licensed_user(interaction.guild_id, interaction.user.id):
            return True
        await interaction.response.send_message(embed=license_required_embed(), ephemeral=True)
        return False

    @discord.ui.button(label="✅  승인", style=discord.ButtonStyle.success, custom_id="charge_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        gid   = self.guild_id
        users = load_guild(gid, "users.json")
        uid   = str(self.user_id)
        if uid not in users:
            users[uid] = {"balance": 0, "purchases": [], "pending_charge": False}
        users[uid]["balance"]        = users[uid].get("balance", 0) + self.amount
        users[uid]["pending_charge"] = False
        save_guild(gid, "users.json", users)
        new_bal = users[uid]["balance"]

        for item in self.children: item.disabled = True
        await interaction.message.edit(view=self)

        de = base_embed("✅ 충전 승인 완료", f"<@{self.user_id}> 님의 충전이 승인되었습니다.", SUCCESS_COLOR)
        de.add_field(name="💰 충전 금액", value=f"**{self.amount:,}원**", inline=True)
        de.add_field(name="💼 현재 잔액", value=f"**{new_bal:,}원**",    inline=True)
        de.add_field(name="👮 처리자",    value=f"{interaction.user.mention}", inline=True)
        await interaction.response.send_message(embed=de)

        try:
            user = await bot.fetch_user(self.user_id)
            dme = base_embed("🎉 충전이 완료되었어요!", "관리자가 입금을 확인하고 잔액을 추가했어요.", SUCCESS_COLOR)
            dme.add_field(name="💰 충전 금액", value=f"**{self.amount:,}원**", inline=True)
            dme.add_field(name="💼 현재 잔액", value=f"**{new_bal:,}원**",    inline=True)
            dme.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/190/190411.png")
            await user.send(embed=dme)
        except: pass

    @discord.ui.button(label="❌  거절", style=discord.ButtonStyle.danger, custom_id="charge_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        gid   = self.guild_id
        users = load_guild(gid, "users.json")
        uid   = str(self.user_id)
        if uid in users:
            users[uid]["pending_charge"] = False
            save_guild(gid, "users.json", users)

        for item in self.children: item.disabled = True
        await interaction.message.edit(view=self)

        re = base_embed("❌ 충전 거절됨", f"<@{self.user_id}> 님의 충전 요청이 거절되었습니다.", ERROR_COLOR)
        re.add_field(name="💰 신청 금액", value=f"**{self.amount:,}원**", inline=True)
        re.add_field(name="👮 처리자",    value=f"{interaction.user.mention}", inline=True)
        await interaction.response.send_message(embed=re)

        try:
            user = await bot.fetch_user(self.user_id)
            dme = base_embed("😥 충전 요청이 거절되었어요",
                "입금자명 또는 금액을 다시 확인한 후\n관리자에게 문의해 주세요.", ERROR_COLOR)
            dme.add_field(name="💰 신청 금액", value=f"**{self.amount:,}원**", inline=True)
            await user.send(embed=dme)
        except: pass


# ─────────────────────────────────────────
#  상품 목록 드롭다운
# ─────────────────────────────────────────
class ProductListSelect(discord.ui.Select):
    def __init__(self, products: dict, guild_id):
        self.guild_id = guild_id
        options = []
        for pid, p in list(products.items())[:25]:
            stock      = len(p.get("accounts", []))
            stock_text = f"재고 {stock}개" if stock > 0 else "품절"
            options.append(discord.SelectOption(
                label=p["name"][:100], value=pid,
                description=f"{p['price']:,}원  ·  {stock_text}"[:100],
                emoji="✅" if stock > 0 else "❌"
            ))
        super().__init__(placeholder="상품을 선택하면 상세 정보를 볼 수 있어요", options=options)

    async def callback(self, interaction: discord.Interaction):
        products = load_guild(self.guild_id, "products.json")
        pid      = self.values[0]
        p        = products.get(pid)
        if not p:
            await interaction.response.send_message(embed=base_embed("❌ 상품 없음", "해당 상품이 삭제되었어요.", ERROR_COLOR), ephemeral=True)
            return
        stock  = len(p.get("accounts", []))
        status = f"✅  재고 {stock}개" if stock > 0 else "❌  품절"
        e = discord.Embed(title=f"🎬  {p['name']}", color=BOT_COLOR)
        e.add_field(name="💰 가격", value=f"**{p['price']:,}원**", inline=True)
        e.add_field(name="📦 재고", value=f"**{stock}개**",        inline=True)
        e.add_field(name="📶 상태", value=status,                  inline=True)
        if p.get("desc"):
            e.add_field(name="📝 설명", value=p["desc"], inline=False)
        e.set_footer(text="rkatmxm OTT · 상품 상세")
        e.timestamp = datetime.utcnow()
        await interaction.response.send_message(embed=e, ephemeral=True)

class ProductListView(discord.ui.View):
    def __init__(self, products: dict, guild_id):
        super().__init__(timeout=60)
        self.add_item(ProductListSelect(products, guild_id))


# ─────────────────────────────────────────
#  구매 내역 드롭다운
# ─────────────────────────────────────────
class HistorySelect(discord.ui.Select):
    def __init__(self, purchases: list):
        recent  = purchases[-25:][::-1]
        options = []
        for i, b in enumerate(recent):
            options.append(discord.SelectOption(
                label=b["product"][:50], value=str(i),
                description=f"{b['price']:,}원  ·  {b['date']}"[:100], emoji="🎬"
            ))
        self._purchases = recent
        super().__init__(placeholder="구매 내역을 선택하면 상세 정보를 볼 수 있어요", options=options)

    async def callback(self, interaction: discord.Interaction):
        b = self._purchases[int(self.values[0])]
        e = discord.Embed(title="📋  구매 상세 내역", color=BOT_COLOR)
        e.add_field(name="🎬 상품명",    value=f"**{b['product']}**",  inline=True)
        e.add_field(name="💰 결제 금액", value=f"**{b['price']:,}원**", inline=True)
        e.add_field(name="📅 구매 시각", value=f"`{b['date']}`",        inline=True)
        e.set_footer(text="rkatmxm OTT · 구매 내역")
        e.timestamp = datetime.utcnow()
        await interaction.response.send_message(embed=e, ephemeral=True)

class HistoryView(discord.ui.View):
    def __init__(self, purchases: list):
        super().__init__(timeout=60)
        self.add_item(HistorySelect(purchases))


# ─────────────────────────────────────────
#  패널 메인 View
# ─────────────────────────────────────────
class ShopPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💰 충전하기", style=discord.ButtonStyle.secondary, custom_id="panel_charge", row=0)
    async def charge_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid   = interaction.guild_id
        users = load_guild(gid, "users.json")
        uid   = str(interaction.user.id)
        if users.get(uid, {}).get("pending_charge"):
            await interaction.response.send_message(embed=base_embed(
                "⏳ 대기 중인 요청 있음",
                "이미 충전 요청이 처리 중이에요.\n관리자가 승인 또는 거절할 때까지 기다려 주세요.", WARN_COLOR
            ), ephemeral=True)
            return
        await interaction.response.send_modal(ChargeModal())

    @discord.ui.button(label="💲 잔액 확인", style=discord.ButtonStyle.secondary, custom_id="panel_balance", row=0)
    async def balance_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid     = interaction.guild_id
        users   = load_guild(gid, "users.json")
        uid     = str(interaction.user.id)
        data    = users.get(uid, {"balance": 0, "purchases": []})
        balance = data.get("balance", 0)
        buys    = data.get("purchases", [])
        e = discord.Embed(color=BOT_COLOR)
        e.set_author(name=f"{interaction.user.display_name}님의 지갑", icon_url=interaction.user.display_avatar.url)
        e.add_field(name="💰 현재 잔액", value=f"```\n{balance:,}원\n```", inline=True)
        e.add_field(name="🧾 총 구매",   value=f"```\n{len(buys)}건\n```",  inline=True)
        if buys:
            recent  = buys[-3:][::-1]
            history = "\n".join([f"› {b['product']}  **{b['price']:,}원**  `{b['date']}`" for b in recent])
            e.add_field(name="📋 최근 구매", value=history, inline=False)
        e.set_footer(text="rkatmxm OTT · 잔액 조회")
        e.timestamp = datetime.utcnow()
        await interaction.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="🛍 상품 보기", style=discord.ButtonStyle.secondary, custom_id="panel_products", row=0)
    async def products_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid      = interaction.guild_id
        products = load_guild(gid, "products.json")
        if not products:
            await interaction.response.send_message(
                embed=base_embed("📦 상품 없음", "현재 등록된 상품이 없어요.", WARN_COLOR),
                ephemeral=True
            )
            return
        e = discord.Embed(title="🛍  판매 중인 상품 목록",
            description="아래 드롭다운에서 상품을 선택하면 상세 정보를 확인할 수 있어요.", color=BOT_COLOR)
        for pid, p in list(products.items())[:25]:
            stock  = len(p.get("accounts", []))
            status = f"✅ 재고 {stock}개" if stock > 0 else "❌ 품절"
            e.add_field(name=f"🎬  {p['name']}", value=f"**{p['price']:,}원**  ·  {status}", inline=True)
        e.set_footer(text="rkatmxm OTT · 상품 목록")
        e.timestamp = datetime.utcnow()
        await interaction.response.send_message(embed=e, view=ProductListView(products, gid), ephemeral=True)

    @discord.ui.button(label="🛒 구매하기", style=discord.ButtonStyle.secondary, custom_id="panel_buy", row=0)
    async def buy_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid      = interaction.guild_id
        products = load_guild(gid, "products.json")
        users    = load_guild(gid, "users.json")
        uid      = str(interaction.user.id)
        balance  = users.get(uid, {}).get("balance", 0)
        avail    = {pid: p for pid, p in products.items() if len(p.get("accounts", [])) > 0}
        if not avail:
            await interaction.response.send_message(
                embed=base_embed("😥 품절", "현재 재고가 있는 상품이 없어요.", WARN_COLOR),
                ephemeral=True
            )
            return
        e = discord.Embed(title="🛒  구매하기",
            description=f"> 현재 잔액 · **{balance:,}원**\n아래에서 구매할 상품을 선택해 주세요.", color=BOT_COLOR)
        e.set_footer(text="rkatmxm OTT · 구매")
        e.timestamp = datetime.utcnow()
        await interaction.response.send_message(embed=e, view=BuySelectView(avail, uid, balance, gid), ephemeral=True)

    @discord.ui.button(label="📋 구매 내역", style=discord.ButtonStyle.secondary, custom_id="panel_history", row=0)
    async def history_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid   = interaction.guild_id
        users = load_guild(gid, "users.json")
        uid   = str(interaction.user.id)
        buys  = users.get(uid, {}).get("purchases", [])
        if not buys:
            await interaction.response.send_message(
                embed=base_embed("📋 구매 내역 없음", "아직 구매한 상품이 없어요.", WARN_COLOR),
                ephemeral=True
            )
            return
        e = discord.Embed(title="📋  구매 내역",
            description=f"총 **{len(buys)}건**의 구매 기록이 있어요.\n아래 드롭다운에서 상세 내역을 확인하세요.", color=BOT_COLOR)
        e.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        e.set_footer(text="rkatmxm OTT · 구매 내역")
        e.timestamp = datetime.utcnow()
        await interaction.response.send_message(embed=e, view=HistoryView(buys), ephemeral=True)


# ─────────────────────────────────────────
#  구매 드롭다운
# ─────────────────────────────────────────
class BuySelectView(discord.ui.View):
    def __init__(self, products, uid, balance, guild_id):
        super().__init__(timeout=60)
        self.add_item(BuySelect(products, uid, balance, guild_id))

class BuySelect(discord.ui.Select):
    def __init__(self, products, uid, balance, guild_id):
        self.uid      = uid
        self.balance  = balance
        self.guild_id = guild_id
        options = [
            discord.SelectOption(
                label=p["name"][:100], value=pid,
                description=f"{p['price']:,}원 | 재고 {len(p['accounts'])}개"[:100],
                emoji="🎬"
            )
            for pid, p in products.items()
        ]
        super().__init__(placeholder="구매할 상품을 선택하세요...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message(embed=base_embed("🚫 오류", "본인의 메뉴만 사용할 수 있어요.", ERROR_COLOR), ephemeral=True)
            return
        gid      = self.guild_id
        products = load_guild(gid, "products.json")
        users    = load_guild(gid, "users.json")
        pid      = self.values[0]
        product  = products.get(pid)
        if not product or not product.get("accounts"):
            await interaction.response.send_message(embed=base_embed("😥 품절", "방금 품절됐어요. 다시 시도해 주세요.", WARN_COLOR), ephemeral=True)
            return
        uid     = str(interaction.user.id)
        balance = users.get(uid, {}).get("balance", 0)
        price   = product["price"]
        if balance < price:
            shortage = price - balance
            e = base_embed("💸 잔액 부족", f"잔액이 **{shortage:,}원** 부족해요.\n충전 후 다시 시도해 주세요.", ERROR_COLOR)
            e.add_field(name="현재 잔액", value=f"{balance:,}원", inline=True)
            e.add_field(name="상품 가격", value=f"{price:,}원",   inline=True)
            await interaction.response.send_message(embed=e, ephemeral=True)
            return
        account = product["accounts"].pop(0)
        users[uid]["balance"] -= price
        users[uid].setdefault("purchases", []).append({
            "product": product["name"], "price": price,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        save_guild(gid, "products.json", products)
        save_guild(gid, "users.json", users)
        new_bal = users[uid]["balance"]
        ok = base_embed("✅ 구매 완료!", f"**{product['name']}** 계정을 DM으로 전송했어요.", SUCCESS_COLOR)
        ok.add_field(name="💰 결제 금액", value=f"{price:,}원",   inline=True)
        ok.add_field(name="💼 남은 잔액", value=f"{new_bal:,}원", inline=True)
        await interaction.response.send_message(embed=ok, ephemeral=True)
        try:
            dm = base_embed(f"🎬 {product['name']} 계정 정보",
                "아래 계정 정보로 로그인하세요.\n**타인과 공유하지 마세요.**", SUCCESS_COLOR)
            dm.add_field(name="📧 계정 정보", value=f"```\n{account}\n```", inline=False)
            dm.add_field(name="💰 결제 금액", value=f"{price:,}원",   inline=True)
            dm.add_field(name="💼 남은 잔액", value=f"{new_bal:,}원", inline=True)
            dm.add_field(name="⚠️ 주의사항",
                value="• 비밀번호 변경 금지\n• 다른 기기 동시 접속 자제\n• 문제 발생 시 관리자 문의", inline=False)
            dm.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/2991/2991195.png")
            user = await bot.fetch_user(int(self.uid))
            await user.send(embed=dm)
        except Exception as ex:
            print(f"DM 전송 실패: {ex}")


# ─────────────────────────────────────────
#  라이센스 관리 View
# ─────────────────────────────────────────
class LicenseManageView(discord.ui.View):
    def __init__(self, gid: str, users_list: list, index: int = 0):
        super().__init__(timeout=120)
        self.gid        = gid
        self.users_list = users_list
        self.index      = index
        self._refresh_nav()

    def _refresh_nav(self):
        self.prev_btn.disabled = (self.index == 0)
        self.next_btn.disabled = (self.index >= len(self.users_list) - 1)

    async def build_embed(self) -> discord.Embed:
        udata     = self.users_list[self.index]
        reg_uid   = udata.get("user_id", 0)
        key_str   = udata.get("key", "알 수 없음")
        reg_at    = udata.get("registered_at", "알 수 없음")
        suspended = udata.get("suspended", False)

        status_icon = "🔴" if suspended else "🟢"
        status_text = "OFFLINE (정지됨)" if suspended else "ONLINE (활성)"
        bar_color   = ERROR_COLOR if suspended else SUCCESS_COLOR

        guild      = bot.get_guild(int(self.gid))
        guild_name = guild.name if guild else f"서버 ID: {self.gid}"
        joined_at  = guild.me.joined_at.strftime("%Y-%m-%d") if guild and guild.me.joined_at else "알 수 없음"

        try:
            reg_user   = await bot.fetch_user(reg_uid)
            display    = reg_user.display_name
            avatar_url = reg_user.display_avatar.url
        except:
            display    = udata.get("registrant_name", "알 수 없음")
            avatar_url = None

        e = discord.Embed(title=f"{status_icon}  {guild_name}", description=f"**{status_text}**", color=bar_color)
        e.add_field(name="👤 등록자 닉네임",   value=f"`{display}`",  inline=True)
        e.add_field(name="🆔 사용자 ID",       value=f"`{reg_uid}`",  inline=True)
        e.add_field(name="🔑 라이센스 키",     value=f"```\n{key_str}\n```", inline=False)
        e.add_field(name="📅 라이센스 시작일", value=f"`{reg_at}`",   inline=True)
        e.add_field(name="🏠 서버 봇 가입일",  value=f"`{joined_at}`", inline=True)
        e.add_field(name="🆔 서버 ID",         value=f"`{self.gid}`", inline=True)
        if avatar_url:
            e.set_thumbnail(url=avatar_url)
        e.set_footer(text=f"rkatmxm0 V2 · 라이센스 관리 ({self.index + 1}/{len(self.users_list)})")
        e.timestamp = datetime.utcnow()
        return e

    async def _update(self, interaction: discord.Interaction):
        self._refresh_nav()
        embed = await self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⬅️ 이전", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index -= 1
        await self._update(interaction)

    @discord.ui.button(label="➡️ 다음", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index += 1
        await self._update(interaction)

    @discord.ui.button(label="⏻  ON / OFF", style=discord.ButtonStyle.primary)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != DEVELOPER_ID:
            await interaction.response.send_message(embed=no_permission_embed(), ephemeral=True)
            return
        licenses     = load("licenses.json")
        guild_lic    = licenses.get(self.gid, {})
        users_in_lic = guild_lic.get("users", [])
        udata        = self.users_list[self.index]
        reg_uid      = udata["user_id"]
        new_suspended = not udata.get("suspended", False)

        for u in users_in_lic:
            if u["user_id"] == reg_uid:
                u["suspended"] = new_suspended
                break
        licenses[self.gid]["users"] = users_in_lic
        save("licenses.json", licenses)
        udata["suspended"] = new_suspended
        await self._update(interaction)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            reg_user = await bot.fetch_user(reg_uid)
            if new_suspended:
                dm_e = discord.Embed(title="🔴  라이센스 오프라인",
                    description="귀하의 라이센스가 **비활성화** 되었습니다.\n모든 관리 명령어 사용이 제한됩니다.", color=ERROR_COLOR)
            else:
                dm_e = discord.Embed(title="🟢  라이센스 온라인",
                    description="귀하의 라이센스가 **재활성화** 되었습니다.\n모든 관리 명령어를 다시 사용할 수 있어요.", color=SUCCESS_COLOR)
            dm_e.add_field(name="📶 현재 상태", value=f"```\n{'OFFLINE' if new_suspended else 'ONLINE'}\n```", inline=True)
            dm_e.add_field(name="🕐 처리 시각", value=f"`{now_str}`", inline=True)
            dm_e.set_footer(text="rkatmxm0 V2 · 라이센스 알림")
            dm_e.timestamp = datetime.utcnow()
            await reg_user.send(embed=dm_e)
        except: pass

    @discord.ui.button(label="🗑️  DELETE", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != DEVELOPER_ID:
            await interaction.response.send_message(embed=no_permission_embed(), ephemeral=True)
            return
        licenses     = load("licenses.json")
        guild_lic    = licenses.get(self.gid, {})
        users_in_lic = guild_lic.get("users", [])
        udata        = self.users_list[self.index]
        reg_uid      = udata["user_id"]
        now_str      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        licenses[self.gid]["users"] = [u for u in users_in_lic if u["user_id"] != reg_uid]
        if not licenses[self.gid]["users"]:
            licenses[self.gid]["active"] = False
        save("licenses.json", licenses)
        self.users_list.pop(self.index)

        try:
            reg_user = await bot.fetch_user(reg_uid)
            dm_e = discord.Embed(title="🗑️  라이센스 제거됨",
                description="귀하의 라이센스가 **삭제**되었습니다.\n모든 명령어 사용이 즉시 차단됩니다.\n\n새 라이센스가 필요하시면 개발자에게 문의해 주세요.",
                color=ERROR_COLOR)
            dm_e.add_field(name="⛔ 현재 상태", value="```\n🗑️ DELETED\n```", inline=True)
            dm_e.add_field(name="🕐 처리 시각", value=f"`{now_str}`",          inline=True)
            dm_e.set_footer(text="rkatmxm0 V2 · 라이센스 알림")
            dm_e.timestamp = datetime.utcnow()
            await reg_user.send(embed=dm_e)
        except: pass

        if not self.users_list:
            await interaction.response.edit_message(
                content="❌ 이 서버의 모든 라이센스가 삭제되었습니다.", embed=None, view=None)
        else:
            if self.index >= len(self.users_list): self.index -= 1
            await self._update(interaction)


# ─────────────────────────────────────────
#  슬래시 커맨드
# ─────────────────────────────────────────
@bot.tree.command(name="패널", description="OTT 자판기 패널을 생성합니다")
async def panel_cmd(interaction: discord.Interaction):
    if not is_licensed_user(interaction.guild_id, interaction.user.id) and interaction.user.id != DEVELOPER_ID:
        await interaction.response.send_message(embed=license_required_embed(), ephemeral=True)
        return
    e = discord.Embed(
        title="rkatmxm  OTT",
        description=(
            "구매를 원하시면 **구매하기**\n"
            "충전을 원하시면 **충전하기**\n"
            "제품을 보고싶으시면 **상품 보기**\n"
            "충전 오류시 티켓 열어주세요"
        ),
        color=0x2B2D31
    )
    e.set_image(url="https://cdn.discordapp.com/attachments/1382640666764382291/1497242804726796298/ChatGPT_Image_2026_4_24_11_37_37.png?ex=69eccf86&is=69eb7e06&hm=b9ea957932b9bf6e81ef23d921a045a5a911d86df862d0c5be9cda0087aa0786&")
    e.set_footer(text="rkatmxm OTT  ·  rkatmxm0 V2")
    e.timestamp = datetime.utcnow()
    await interaction.response.send_message(embed=e, view=ShopPanelView())


@bot.tree.command(name="상품등록", description="상품을 등록합니다")
@app_commands.describe(상품id="상품 고유 ID (영문, 예: netflix)", 이름="상품 이름", 가격="가격 (원)", 설명="상품 설명")
async def add_product(interaction: discord.Interaction, 상품id: str, 이름: str, 가격: int, 설명: str = ""):
    if not is_licensed_user(interaction.guild_id, interaction.user.id) and interaction.user.id != DEVELOPER_ID:
        await interaction.response.send_message(embed=license_required_embed(), ephemeral=True)
        return
    gid      = interaction.guild_id
    products = load_guild(gid, "products.json")
    if 상품id in products:
        await interaction.response.send_message(
            embed=base_embed("⚠️ 이미 존재하는 ID", f"`{상품id}` ID는 이미 사용 중이에요.", WARN_COLOR),
            ephemeral=True
        )
        return
    products[상품id] = {"name": 이름, "price": 가격, "desc": 설명, "accounts": []}
    save_guild(gid, "products.json", products)
    e = base_embed("✅ 상품 등록 완료", "", SUCCESS_COLOR)
    e.add_field(name="상품명", value=이름,          inline=True)
    e.add_field(name="가격",   value=f"{가격:,}원", inline=True)
    await interaction.response.send_message(embed=e, ephemeral=True)


@bot.tree.command(name="계정추가", description="상품에 계정을 추가합니다")
@app_commands.describe(상품id="상품 ID", 계정정보="계정 정보 (예: id@email.com / password123)")
async def add_account(interaction: discord.Interaction, 상품id: str, 계정정보: str):
    if not is_licensed_user(interaction.guild_id, interaction.user.id) and interaction.user.id != DEVELOPER_ID:
        await interaction.response.send_message(embed=license_required_embed(), ephemeral=True)
        return
    gid      = interaction.guild_id
    products = load_guild(gid, "products.json")
    if 상품id not in products:
        await interaction.response.send_message(
            embed=base_embed("❌ 없는 상품", f"`{상품id}` 상품이 없어요.", ERROR_COLOR),
            ephemeral=True
        )
        return
    products[상품id]["accounts"].append(계정정보)
    save_guild(gid, "products.json", products)
    stock = len(products[상품id]["accounts"])
    await interaction.response.send_message(
        embed=base_embed("✅ 계정 추가 완료", f"**{products[상품id]['name']}** — 현재 재고: {stock}개", SUCCESS_COLOR),
        ephemeral=True
    )


@bot.tree.command(name="상품삭제", description="상품을 삭제합니다")
@app_commands.describe(상품id="삭제할 상품 ID")
async def del_product(interaction: discord.Interaction, 상품id: str):
    if not is_licensed_user(interaction.guild_id, interaction.user.id) and interaction.user.id != DEVELOPER_ID:
        await interaction.response.send_message(embed=license_required_embed(), ephemeral=True)
        return
    gid      = interaction.guild_id
    products = load_guild(gid, "products.json")
    if 상품id not in products:
        await interaction.response.send_message(embed=base_embed("❌ 없는 상품", "", ERROR_COLOR), ephemeral=True)
        return
    name = products.pop(상품id)["name"]
    save_guild(gid, "products.json", products)
    await interaction.response.send_message(
        embed=base_embed("🗑️ 상품 삭제 완료", f"**{name}** 이(가) 삭제되었어요.", SUCCESS_COLOR),
        ephemeral=True
    )


@bot.tree.command(name="잔액지급", description="유저에게 잔액을 직접 지급합니다")
@app_commands.describe(유저="대상 유저", 금액="지급할 금액")
async def give_balance(interaction: discord.Interaction, 유저: discord.Member, 금액: int):
    if not is_licensed_user(interaction.guild_id, interaction.user.id) and interaction.user.id != DEVELOPER_ID:
        await interaction.response.send_message(embed=license_required_embed(), ephemeral=True)
        return
    gid   = interaction.guild_id
    users = load_guild(gid, "users.json")
    uid   = str(유저.id)
    if uid not in users:
        users[uid] = {"balance": 0, "purchases": [], "pending_charge": False}
    users[uid]["balance"] += 금액
    save_guild(gid, "users.json", users)
    e = base_embed("✅ 잔액 지급 완료", "", SUCCESS_COLOR)
    e.add_field(name="유저",      value=유저.mention,                   inline=True)
    e.add_field(name="지급 금액", value=f"{금액:,}원",                  inline=True)
    e.add_field(name="현재 잔액", value=f"{users[uid]['balance']:,}원", inline=True)
    await interaction.response.send_message(embed=e, ephemeral=True)


# ─────────────────────────────────────────
#  라이센스 생성 (개발자 전용)
# ─────────────────────────────────────────
@bot.tree.command(name="라이센스생성", description="[개발자 전용] 새 라이센스 키를 생성합니다")
async def create_license(interaction: discord.Interaction):
    if interaction.user.id != DEVELOPER_ID:
        await interaction.response.send_message(embed=no_permission_embed(), ephemeral=True)
        return
    key     = generate_license_key()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    licenses = load("licenses.json")
    licenses.setdefault("pending_keys", {})[key] = {"created_at": now_str, "used": False}
    save("licenses.json", licenses)
    await interaction.response.send_message("✅ 라이센스 키가 생성되었어요. **개인 메시지**를 확인하세요.", ephemeral=True)
    try:
        dev  = await bot.fetch_user(DEVELOPER_ID)
        dm_e = discord.Embed(
            title="🔑  새 라이센스 키 발급",
            description="아래 키를 복사해서 사용하세요.\n이 키는 **1회용**이며 한 명이 등록 가능해요.",
            color=GOLD_COLOR
        )
        dm_e.add_field(name="━━━━━━  라이센스 키  ━━━━━━", value=f"```\n{key}\n```", inline=False)
        dm_e.add_field(name="📅 발급 시각",      value=f"`{now_str}`", inline=True)
        dm_e.add_field(name="♻️ 사용 가능 횟수", value="`1회`",        inline=True)
        dm_e.add_field(name="📌 등록 방법",       value="`/라이센스등록` 명령어에 키를 입력하세요", inline=False)
        dm_e.set_author(name="rkatmxm0 V2 · 라이센스 시스템", icon_url=bot.user.display_avatar.url)
        dm_e.set_footer(text="이 키를 타인에게 공유하지 마세요")
        dm_e.timestamp = datetime.utcnow()
        await dev.send(embed=dm_e)
    except Exception as ex:
        print(f"개발자 DM 전송 실패: {ex}")


# ─────────────────────────────────────────
#  라이센스 등록
# ─────────────────────────────────────────
@bot.tree.command(name="라이센스등록", description="라이센스 키를 입력해 이 서버를 활성화합니다")
@app_commands.describe(키="발급받은 라이센스 키 (XXXX-XXXX-XXXX-XXXX)")
async def register_license(interaction: discord.Interaction, 키: str):
    키       = 키.strip().upper()
    licenses = load("licenses.json")
    gid      = str(interaction.guild_id)
    uid      = interaction.user.id

    pending = licenses.get("pending_keys", {})
    if 키 not in pending or pending[키].get("used"):
        e = discord.Embed(title="❌  유효하지 않은 키",
            description="입력한 라이센스 키가 올바르지 않거나\n이미 사용된 키예요.\n\n개발자에게 문의해 새 키를 발급받으세요.",
            color=ERROR_COLOR)
        e.set_footer(text="rkatmxm0 V2 · 라이센스 시스템")
        e.timestamp = datetime.utcnow()
        await interaction.response.send_message(embed=e, ephemeral=True)
        return

    guild_lic    = licenses.get(gid, {"active": True, "suspended": False, "users": []})
    users_in_lic = guild_lic.get("users", [])
    if any(u["user_id"] == uid for u in users_in_lic):
        e = discord.Embed(title="✅  이미 등록됨", description="이미 이 서버에 라이센스가 등록되어 있어요!", color=SUCCESS_COLOR)
        e.set_footer(text="rkatmxm0 V2 · 라이센스 시스템")
        e.timestamp = datetime.utcnow()
        await interaction.response.send_message(embed=e, ephemeral=True)
        return

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pending[키]["used"] = True
    licenses["pending_keys"] = pending

    users_in_lic.append({
        "user_id":         uid,
        "key":             키,
        "registered_at":   now_str,
        "registrant_name": str(interaction.user),
        "suspended":       False
    })
    guild_lic["active"] = True
    guild_lic["users"]  = users_in_lic
    licenses[gid]       = guild_lic
    save("licenses.json", licenses)

    e = discord.Embed(
        title="🎉  라이센스 등록 완료!",
        description=f"**{interaction.guild.name}** 서버에 라이센스가 등록되었어요.\n이제 자판기 관리 명령어를 사용할 수 있어요!",
        color=GOLD_COLOR
    )
    e.add_field(name="🔑 등록된 키",  value=f"```\n{키}\n```",            inline=False)
    e.add_field(name="👤 등록자",     value=f"{interaction.user.mention}", inline=True)
    e.add_field(name="📅 등록 시각",  value=f"`{now_str}`",                inline=True)
    e.add_field(name="🏠 서버",       value=f"`{interaction.guild.name}`", inline=True)
    e.add_field(name="✅ 사용 가능한 명령어",
        value="`/패널`  `/상품등록`  `/계정추가`\n`/상품삭제`  `/잔액지급`", inline=False)
    e.set_author(name=interaction.guild.name,
        icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
    e.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/190/190411.png")
    e.set_footer(text="rkatmxm0 V2 · 라이센스 활성화 완료")
    e.timestamp = datetime.utcnow()
    await interaction.response.send_message(embed=e, ephemeral=True)

    try:
        dev   = await bot.fetch_user(DEVELOPER_ID)
        guild = interaction.guild
        dm_e  = discord.Embed(
            title="🔔  새 라이센스 등록 알림",
            description="새로운 사용자가 라이센스를 등록했어요.",
            color=GOLD_COLOR
        )
        dm_e.add_field(name="👤 등록자 닉네임", value=f"`{interaction.user.display_name}`", inline=True)
        dm_e.add_field(name="🆔 등록자 ID",     value=f"`{uid}`",                           inline=True)
        dm_e.add_field(name="🏠 서버 이름",     value=f"`{guild.name}`",                    inline=True)
        dm_e.add_field(name="🆔 서버 ID",       value=f"`{gid}`",                           inline=True)
        dm_e.add_field(name="🕐 등록 시각",     value=f"`{now_str}`",                       inline=True)
        dm_e.add_field(name="🔑 사용된 키",     value=f"```\n{키}\n```",                    inline=False)
        dm_e.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        dm_e.set_thumbnail(url=guild.icon.url if guild.icon else interaction.user.display_avatar.url)
        dm_e.set_footer(text="rkatmxm0 V2 · 라이센스 등록 알림")
        dm_e.timestamp = datetime.utcnow()
        await dev.send(embed=dm_e)
    except Exception as ex:
        print(f"개발자 DM 전송 실패: {ex}")


# ─────────────────────────────────────────
#  라이센스 관리 (개발자 전용)
# ─────────────────────────────────────────
@bot.tree.command(name="라이센스관리", description="[개발자 전용] 이 서버의 라이센스 사용자를 관리합니다")
async def manage_licenses(interaction: discord.Interaction):
    if interaction.user.id != DEVELOPER_ID:
        await interaction.response.send_message(embed=no_permission_embed(), ephemeral=True)
        return

    gid          = str(interaction.guild_id)
    licenses     = load("licenses.json")
    guild_lic    = licenses.get(gid, {})
    users_in_lic = guild_lic.get("users", [])

    if not users_in_lic:
        e = discord.Embed(title="📋  라이센스 관리",
            description="이 서버에 등록된 라이센스 사용자가 없어요.", color=WARN_COLOR)
        e.set_footer(text="rkatmxm0 V2 · 라이센스 관리")
        e.timestamp = datetime.utcnow()
        await interaction.response.send_message(embed=e, ephemeral=True)
        return

    view  = LicenseManageView(gid=gid, users_list=list(users_in_lic), index=0)
    embed = await view.build_embed()
    view._refresh_nav()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ─────────────────────────────────────────
#  봇 시작
# ─────────────────────────────────────────
@bot.event
async def on_ready():
    bot.add_view(ShopPanelView())
    bot.add_view(ChargeApproveView(0, 0, "", 0))
    await bot.tree.sync()
    print(f"✅ {bot.user} 로그인 완료 | 서버 {len(bot.guilds)}개")

bot.run(BOT_TOKEN)