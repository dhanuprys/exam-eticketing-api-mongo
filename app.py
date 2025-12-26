# Di-format menggunakan yapf [google style]

##################################################################
# FHIS Enjoyer Team
##################################################################
# 1. I Kadek Sindu Arta (24150910918)
# 2. Made Marsel Biliana Wijaya (2415091090)
# 3. Gede Dhanu Purnayasa (2415091092)
##################################################################

import random
import uvicorn
from fastapi.exceptions import RequestValidationError
from pydantic_core import ErrorDetails
from pymongo.errors import DuplicateKeyError
from typing import Literal, Generic, TypeVar, List
from starlette.exceptions import HTTPException as StarletteHTTPException
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator
from contextlib import asynccontextmanager
from pydantic_settings import SettingsConfigDict
from fastapi import FastAPI, APIRouter, status, Request, Depends
from fastapi.responses import JSONResponse
from pydantic_settings import BaseSettings
from pymongo import AsyncMongoClient
from typing import Optional
from bson.objectid import ObjectId
from beanie import init_beanie, Document, Indexed

# [DICT&CONSTANT]
# Untuk memastikan error code pada response API selalu konsisten.
# Kami memutuskan untuk menggunakan dictionary, sehingga error_code
# dan message-nya selalu konsisten
ERROR_CODE_DICT = {
    "EVENT_NOT_FOUND": {
        "code": "EVENT_NOT_FOUND",
        "message": "event not found"
    },
    "INVALID_QUOTA": {
        "code": "INVALID_QUOTA",
        "message": "ticket quota cannot be less than ticket stock"
    },
    "QUOTA_EXHAUSTED": {
        "code": "INVALID_QUOTA",
        "message": "ticket quota exhausted"
    },
    "TICKET_NOT_FOUND": {
        "code": "TICKET_NOT_FOUND",
        "message": "ticket not found"
    },
    "EVENT_NOT_STARTED": {
        "code": "EVENT_NOT_STARTED",
        "message": "event not started"
    },
    "EVENT_ENDED": {
        "code": "EVENT_ENDED",
        "message": "event ended"
    },
    "TICKET_ALREADY_USED": {
        "code": "TICKET_ALREADY_USED",
        "message": "ticket already used"
    },
    "MONGO_CONNECTION_ERROR": {
        "code": "MONGO_CONNECTION_ERROR",
        "message": "mongo connection error"
    },
    "TICKET_GENERATION_FAILED": {
        "code": "SERVER-500",
        "message": "failed to generate unique ticket code"
    },
    "INVALID_OBJECT_ID": {
        "code": "INVALID_OBJECT_ID",
        "message": "invalid object id format"
    }
}

# [/DICT&CONTSTANT]


# [UTIL]
class Settings(BaseSettings):
    """
    Kelas untuk mengatur konfigurasi aplikasi (pydantic-settings)
    """
    model_config = SettingsConfigDict(env_file=".env",
                                      env_file_encoding="utf-8")

    db_url: str = "mongodb://localhost:27017"
    db_name: str = "ticketingsystem"
    host: str = "0.0.0.0"
    port: int = 8050


class ErrorModel(BaseModel):
    """
    Model untuk detail dari "error" pada HTTP response
    """
    code: str
    message: str
    fields: Optional[List[ErrorDetails]] = []


T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """
    Model untuk response dari API untuk menjaga agar
    struktur response selalu konsisten dan mempermudah
    melakukan dokumentasi pada swagger
    """
    model_config = ConfigDict(json_encoders={ObjectId: str})

    success: bool
    message: str
    data: Optional[T] = None
    error: Optional[ErrorModel] = None
    meta: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def auto_fill_meta(self) -> 'APIResponse':
        """
        Otomatis menambahkan "timestamp" ke dalam "meta"
        untuk memudahkan debugging nantinya
        """
        self.meta["timestamp"] = datetime.now().isoformat()
        return self


class APIError(Exception):
    """
    Exception khusus untuk API yang akan
    menghasilkan response dengan struktur
    yang jelas dan mudah di-format
    """

    def __init__(self,
                 status_code: int,
                 error_code: str,
                 error_message: str = None):
        self.status_code = status_code

        if error_code in ERROR_CODE_DICT:
            self.error_code = ERROR_CODE_DICT[error_code]["code"]
            self.error_message = error_message or ERROR_CODE_DICT[error_code][
                "message"]
        else:
            self.error_code = error_code
            self.error_message = error_message


# digunakana ketika membuat ticket (membeli tiket)
def generate_ticket_code():
    return f"MANBD-{random.randint(100000, 999999)}"


# menggunakan "Depends" pattern untuk memastikan bahwa id yang diterima adalah valid
def validate_object_id(id_str: str):
    if not ObjectId.is_valid(id_str):
        raise APIError(status_code=status.HTTP_400_BAD_REQUEST,
                       error_code="INVALID_OBJECT_ID")
    return id_str


def valid_event_id(event_id: str):
    return validate_object_id(event_id)


def valid_ticket_id(ticket_id: str):
    return validate_object_id(ticket_id)


# [/UTIL]


# [ENTITY]
class TicketSold(Document):
    """
    Model untuk tiket yang telah terjual
    """
    event_id: str = Indexed()
    code: str = Indexed(unique=True)
    payment_method: Literal["cash", "online"]
    base_price: float
    final_price: float
    status: Literal["used", "unused"] = Indexed()
    used_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "tickets_sold"


class Event(Document):
    """
    Model untuk event yang akan diadakan
    """
    name: str
    description: str
    start_date: datetime
    end_date: datetime
    location: str
    ticket_base_price: float
    ticket_quota: int
    ticket_stock: int
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "events"


# [/ENTITY]


# [RequestResponse]
class CreateEventRequest(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    description: str = Field(min_length=10)
    start_date: datetime
    end_date: datetime
    location: str = Field(min_length=3)
    ticket_base_price: float = Field(ge=0)
    ticket_quota: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_dates(self) -> 'CreateEventRequest':
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class EventListResponse(BaseModel):
    name: str
    description: str
    start_date: datetime
    end_date: datetime


class EventDetailResponse(BaseModel):
    name: str
    description: str
    start_date: datetime
    end_date: datetime
    location: str
    ticket_base_price: float
    ticket_quota: int
    ticket_stock: int


class EventInsightResponse(BaseModel):
    total_revenue: float
    total_attendees: int
    ticket_sold_count: int


class TicketListResponse(BaseModel):
    code: str
    base_price: float
    final_price: float
    payment_method: Literal["cash", "online"]
    status: Literal["used", "unused"]


class CreateTicketRequest(BaseModel):
    payment_method: Literal["cash", "online"]


# [/RequestResponse]


# [SERVICE]
class EventService():

    async def get_events(self):
        return await Event.find().project(EventListResponse).to_list()

    async def create_event(self, request: CreateEventRequest):
        return await Event(
            **request.dict(),
            ticket_stock=request.ticket_quota,
        ).insert()

    async def update_event(self, event_id: str, request: CreateEventRequest):
        event = await Event.find_one({"_id": ObjectId(event_id)})
        if not event:
            raise APIError(status_code=status.HTTP_404_NOT_FOUND,
                           error_code="EVENT_NOT_FOUND")

        # Quota validation: cannot reduce quota below what is already sold
        sold_count = await TicketSold.find({"event_id": event_id}).count()

        if request.ticket_quota < sold_count:
            raise APIError(status_code=status.HTTP_400_BAD_REQUEST,
                           error_code="INVALID_QUOTA")

        # Calculate the difference BEFORE modifying event object
        # This prevents race conditions where sales happen during update
        quota_diff = request.ticket_quota - event.ticket_quota

        for key, value in request.dict().items():
            setattr(event, key, value)

        # Update fields and increment stock atomically
        await event.update({
            "$set": {
                **request.dict(exclude={"ticket_quota"}), "ticket_quota":
                request.ticket_quota,
                "updated_at": datetime.now()
            },
            "$inc": {
                "ticket_stock": quota_diff
            }
        })

        # Fetch updated document to return
        return await Event.find_one({"_id": ObjectId(event_id)})

    async def delete_event(self, event_id: str):
        event = await Event.find_one({"_id": ObjectId(event_id)})
        if not event:
            raise APIError(status_code=status.HTTP_404_NOT_FOUND,
                           error_code="EVENT_NOT_FOUND")
        await event.delete()

    async def get_event(self, event_id: str):
        event = await Event.find_one({
            "_id": ObjectId(event_id)
        }).project(EventDetailResponse)
        if not event:
            raise APIError(status_code=status.HTTP_404_NOT_FOUND,
                           error_code="EVENT_NOT_FOUND")
        return event

    async def get_event_insights(self, event_id: str):
        event = await Event.find_one({"_id": ObjectId(event_id)})
        if not event:
            raise APIError(status_code=status.HTTP_404_NOT_FOUND,
                           error_code="EVENT_NOT_FOUND")

        pipeline = [{
            "$match": {
                "event_id": event_id
            }
        }, {
            "$group": {
                "_id": None,
                "total_revenue": {
                    "$sum": "$final_price"
                },
                "ticket_sold_count": {
                    "$sum": 1
                },
                "total_attendees": {
                    "$sum": {
                        "$cond": [{
                            "$eq": ["$status", "used"]
                        }, 1, 0]
                    }
                }
            }
        }]
        result = await TicketSold.aggregate(pipeline).to_list()
        if not result:
            return EventInsightResponse(total_revenue=0,
                                        total_attendees=0,
                                        ticket_sold_count=0)

        return EventInsightResponse(
            total_revenue=result[0]["total_revenue"],
            total_attendees=result[0]["total_attendees"],
            ticket_sold_count=result[0]["ticket_sold_count"])


class TicketService():

    async def get_tickets(self, event_id: str):
        return await TicketSold.find({
            "event_id": event_id
        }).project(TicketListResponse).to_list()

    async def create_ticket(self, event_id: str,
                            payment_method: Literal["cash", "online"]):
        event = await Event.find_one({"_id": ObjectId(event_id)})
        if not event:
            raise APIError(status_code=status.HTTP_404_NOT_FOUND,
                           error_code="EVENT_NOT_FOUND")

        # Store base_price BEFORE atomic update (update returns UpdateResult, not Event)
        base_price = event.ticket_base_price

        # Mengurangi stock ticket pada event terkait
        # Menggunakan atomic operator untuk menghindari race condition
        result = await Event.find_one({
            "_id": ObjectId(event_id),
            "ticket_stock": {
                "$gt": 0
            }
        }).update({"$inc": {
            "ticket_stock": -1
        }})

        # Jika quota kurang dari ticket yang sudah terjual
        if result.modified_count == 0:
            raise APIError(status_code=status.HTTP_400_BAD_REQUEST,
                           error_code="QUOTA_EXHAUSTED")

        # Jika menggunakan pembayaran "online" maka
        # akan ditambahkan sebesar 25% dari base_price
        final_price = base_price
        if payment_method == "online":
            final_price += base_price * 0.25

        # Memastikan agar tidak ada ticket dengan kode yang sama
        attempt = 0
        MAX_RETRIES = 10

        while True:
            # Mencegah infinite loop
            # Mungkin bisa diakibatkan oleh koneksi database yang mati
            # sehingga tidak ada response dari update
            if attempt >= MAX_RETRIES:
                raise APIError(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    error_code="TICKET_GENERATION_FAILED")

            try:
                ticket = await TicketSold(
                    event_id=event_id,
                    code=generate_ticket_code(),
                    base_price=base_price,
                    final_price=final_price,
                    payment_method=payment_method,
                    status="unused",
                ).insert()

                break
            except DuplicateKeyError:
                attempt += 1
                continue

        return ticket

    async def delete_ticket(self, event_id: str, ticket_id: str):
        ticket = await TicketSold.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise APIError(status_code=status.HTTP_404_NOT_FOUND,
                           error_code="TICKET_NOT_FOUND")

        # Menghapus ticket dan langsung menggunakan atomic operator
        # untuk menambahkan stock ticket pada event terkait
        await ticket.delete()
        await Event.find_one({
            "_id": ObjectId(event_id)
        }).update({"$inc": {
            "ticket_stock": 1
        }})

    async def use_ticket(self, ticket_id: str):
        # Memastikan apakah ticket dan event nya tersedia dan valid
        ticket = await TicketSold.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise APIError(status_code=status.HTTP_404_NOT_FOUND,
                           error_code="TICKET_NOT_FOUND")
        event = await Event.find_one({"_id": ObjectId(ticket.event_id)})
        if not event:
            raise APIError(status_code=status.HTTP_404_NOT_FOUND,
                           error_code="EVENT_NOT_FOUND")

        # Jika event belum dimulai
        if event.start_date > datetime.now():
            raise APIError(status_code=status.HTTP_400_BAD_REQUEST,
                           error_code="EVENT_NOT_STARTED")
        # Jika event sudah berakhir
        elif event.end_date < datetime.now():
            raise APIError(status_code=status.HTTP_400_BAD_REQUEST,
                           error_code="EVENT_ENDED")

        ticket = await TicketSold.find_one({
            "_id": ObjectId(ticket_id),
            "status": "unused"
        }).update({"$set": {
            "status": "used",
            "used_at": datetime.now()
        }})

        if ticket.modified_count == 0:
            raise APIError(status_code=status.HTTP_400_BAD_REQUEST,
                           error_code="TICKET_ALREADY_USED")


# [/SERVICE]


# [CONTROLLER]
class UtilController():
    """
    Menangani segala resource yang berhubungan dengan 
    hal-hal opsional (seperti health check, root page, dll)
    """
    router = APIRouter()

    def __init__(self, root_router: APIRouter):
        self.router = APIRouter(tags=["utils"])
        self.root_router = root_router

        self._init_router()

    def root_page(self):
        """
        Root page. Menampilkan informasi tentang API
        """
        return APIResponse(success=True,
                           message="ManBD Ticketing API",
                           data={
                               "members": [
                                   "Gede Dhanu Purnayasa",
                                   "Made Marsel Biliana Wijaya",
                                   "I Kadek Sindu Arta"
                               ],
                               "techstack": [
                                   "FastAPI", "Pydantic", "Pydantic Settings",
                                   "Beanie", "MongoDB (PyMongo)", "Python"
                               ]
                           })

    async def reset_database(self):
        """
        Reset database. Digunakan untuk kebutuhan development dan latihan
        """
        await Event.delete_many({})
        await TicketSold.delete_many({})
        return APIResponse(success=True, message="database reset successful")

    async def health_check(self):
        """
        Health check to mongo
        """
        try:
            await Event.find_one({})
        except Exception as e:
            raise APIError(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                           error_code="MONGO_CONNECTION_ERROR")

        return APIResponse(success=True, message="health check successful")

    def _init_router(self):
        self.root_router.add_api_route("/",
                                       self.root_page,
                                       methods=["GET"],
                                       response_model=APIResponse[dict])
        self.root_router.add_api_route("/health",
                                       self.health_check,
                                       methods=["GET"],
                                       response_model=APIResponse[None])
        self.router.add_api_route("/reset-database",
                                  self.reset_database,
                                  methods=["GET", "POST"],
                                  response_model=APIResponse[None])


class EventController():
    """
    Menangani segala resource yang berhubungan dengan event
    """
    router = APIRouter()

    def __init__(self, *, event_service: EventService):
        self.router = APIRouter(tags=["events"])
        self.event_service = event_service

        self._init_router()

    async def get_events(self):
        """
        Mengambil semua event
        """
        events = await self.event_service.get_events()
        return APIResponse(success=True,
                           message="events fetched successfully",
                           data=events)

    async def create_event(self, request: CreateEventRequest):
        """
        Membuat event baru
        """
        event = await self.event_service.create_event(request)
        return APIResponse(success=True,
                           message="event created successfully",
                           data=event)

    async def update_event(self,
                           request: CreateEventRequest,
                           event_id: str = Depends(valid_event_id)):
        """
        Mengupdate event
        """
        event = await self.event_service.update_event(event_id, request)
        return APIResponse(success=True,
                           message="event updated successfully",
                           data=event)

    async def delete_event(self, event_id: str = Depends(valid_event_id)):
        """
        Menghapus event
        """
        await self.event_service.delete_event(event_id)
        return APIResponse(success=True, message="event deleted successfully")

    async def get_event(self, event_id: str = Depends(valid_event_id)):
        """
        Mengambil event
        """
        event = await self.event_service.get_event(event_id)
        return APIResponse(success=True,
                           message="event fetched successfully",
                           data=event)

    async def get_event_insights(self,
                                 event_id: str = Depends(valid_event_id)):
        """
        Mengambil rangkuman event
        """
        data = await self.event_service.get_event_insights(event_id)
        return APIResponse(success=True,
                           message="event insights fetched successfully",
                           data=data)

    def _init_router(self):
        self.router.add_api_route(
            "/events",
            self.get_events,
            methods=["GET"],
            response_model=APIResponse[List[EventListResponse]],
        )
        self.router.add_api_route(
            "/events",
            self.create_event,
            methods=["POST"],
            response_model=APIResponse[Event],
            status_code=status.HTTP_201_CREATED,
        )
        self.router.add_api_route(
            "/events/{event_id}",
            self.update_event,
            methods=["PUT"],
            response_model=APIResponse[Event],
        )
        self.router.add_api_route(
            "/events/{event_id}",
            self.delete_event,
            methods=["DELETE"],
            response_model=APIResponse[None],
        )
        self.router.add_api_route(
            "/events/{event_id}",
            self.get_event,
            methods=["GET"],
            response_model=APIResponse[EventDetailResponse],
        )
        self.router.add_api_route(
            "/events/{event_id}/insights",
            self.get_event_insights,
            methods=["GET"],
            response_model=APIResponse[EventInsightResponse],
        )


class TicketController():
    """
    Menangani segala resource yang berhubungan dengan manajemen tiket
    """
    router = APIRouter()

    def __init__(self, *, ticket_service: TicketService):
        self.router = APIRouter(tags=["tickets"])
        self.ticket_service = ticket_service

        self._init_router()

    async def get_tickets(self, event_id: str = Depends(valid_event_id)):
        """
        Mengambil semua tiket
        """
        tickets = await self.ticket_service.get_tickets(event_id)
        return APIResponse(success=True,
                           message="tickets fetched successfully",
                           data=tickets)

    async def create_ticket(self,
                            request: CreateTicketRequest,
                            event_id: str = Depends(valid_event_id)):
        """
        Membuat tiket baru
        """
        ticket = await self.ticket_service.create_ticket(
            event_id, request.payment_method)
        return APIResponse(success=True,
                           message="ticket created successfully",
                           data=ticket)

    async def delete_ticket(self,
                            event_id: str = Depends(valid_event_id),
                            ticket_id: str = Depends(valid_ticket_id)):
        """
        Menghapus tiket
        """
        await self.ticket_service.delete_ticket(event_id, ticket_id)
        return APIResponse(success=True, message="ticket deleted successfully")

    async def use_ticket(self, ticket_id: str = Depends(valid_ticket_id)):
        """
        Menggunakan tiket (check-in)
        """
        await self.ticket_service.use_ticket(ticket_id)
        return APIResponse(success=True, message="ticket used successfully")

    def _init_router(self):
        self.router.add_api_route(
            "/tickets",
            self.get_tickets,
            methods=["GET"],
            response_model=APIResponse[List[TicketListResponse]],
        )
        self.router.add_api_route(
            "/events/{event_id}/tickets",
            self.create_ticket,
            methods=["POST"],
            response_model=APIResponse[TicketSold],
            status_code=status.HTTP_201_CREATED,
        )
        self.router.add_api_route(
            "/tickets/{ticket_id}",
            self.delete_ticket,
            methods=["DELETE"],
            response_model=APIResponse[None],
        )
        self.router.add_api_route(
            "/tickets/{ticket_id}/check-in",
            self.use_ticket,
            methods=["POST"],
            response_model=APIResponse[None],
        )


# [/CONTROLLER]


# [MAIN]
class Application():

    def __init__(self):
        # Load .env dan simpan pada variabel global
        self.settings = Settings()
        self.app = FastAPI(lifespan=self.lifespan)
        self.db_client: AsyncMongoClient = None

        self._start_up()

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        # Setup DB
        self.db_client = AsyncMongoClient(self.settings.db_url)
        self.db = self.db_client[self.settings.db_name]

        # Initialize Beanie
        # Beanie requires Motor (AsyncIOMotorClient)
        await init_beanie(database=self.db,
                          document_models=[Event, TicketSold])

        yield

        # Menutup koneksi
        await self.db_client.close()

    def _start_up(self):
        self.app.add_exception_handler(APIError, self._api_exception_handler)
        self.app.add_exception_handler(StarletteHTTPException,
                                       self._starlette_exception_handler)
        self.app.add_exception_handler(RequestValidationError,
                                       self._request_exception_handler)
        self.app.add_exception_handler(Exception,
                                       self._global_exception_handler)

        # Setup service
        event_service = EventService()
        ticket_service = TicketService()

        # setup controller
        event_controller = EventController(event_service=event_service)
        ticket_controller = TicketController(ticket_service=ticket_service)
        util_controller = UtilController(root_router=self.app.router)

        # Setup controller dan router
        api_v1_router = APIRouter(prefix="/api/v1")
        api_v1_router.include_router(event_controller.router)
        api_v1_router.include_router(ticket_controller.router)
        api_v1_router.include_router(util_controller.router)

        # Mendaftarkan semua route ke dalam fastAPI
        self.app.include_router(api_v1_router)

    async def _api_exception_handler(self, request: Request, exc: APIError):
        """
        Handler untuk menangani exception yang di-raise oleh API
        """
        response_model = APIResponse(
            success=False,
            message=exc.error_message,
            error=ErrorModel(
                code=exc.error_code,
                message=exc.error_message,
            ),
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=response_model.model_dump(mode="json"),
        )

    async def _starlette_exception_handler(self, request: Request,
                                           exc: StarletteHTTPException):
        """
        Handler untuk menangani exception yang di-raise oleh Starlette
        (biasanya terkait exception HTTP)
        """
        response_model = APIResponse(
            success=False,
            message=exc.detail,
            error=ErrorModel(
                code="STARLETTE-" + str(exc.status_code),
                message=exc.detail,
            ),
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=response_model.model_dump(mode="json"),
        )

    async def _request_exception_handler(self, request: Request,
                                         exc: RequestValidationError):
        """
        Handler untuk menangani exception yang di-raise oleh pydantic
        yang akan memberikan response error konsisten ketika terjadi
        form validation error
        """
        response_model = APIResponse(
            success=False,
            message="Validation Error",
            error=ErrorModel(code="PYDANTIC-422",
                             message="Validation Error",
                             fields=exc.errors()),
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=response_model.model_dump(mode="json"),
        )

    async def _global_exception_handler(self, request: Request,
                                        exc: Exception):
        """
        Handler untuk menangani exception yang di-raise oleh FastAPI
        yang akan memberikan response error konsisten ketika terjadi
        exception yang tidak terduga
        """
        response_model = APIResponse(
            success=False,
            message="Internal Server Error",
            error=ErrorModel(
                code="SERVER-500",
                message="Internal Server Error",
            ),
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response_model.model_dump(mode="json"),
        )


# Menyiapkan instance untuk command "uvicorn"
instance = Application()
main = instance.app

# Jika dieksekusi sebagai script utama, jalankan uvicorn
if __name__ == "__main__":
    print("[Eksekusi langsung]")
    uvicorn.run(instance.app,
                host=instance.settings.host,
                port=instance.settings.port)
else:
    print("[Menggunakan uvicorn sebagai executor]")

# [/MAIN]
