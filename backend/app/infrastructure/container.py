"""The only dependency composition root."""

from dataclasses import dataclass

from app.application.dtos.auth import AuthPolicyDTO
from app.application.dtos.storage import UploadPolicyDTO
from app.application.ports.auth_services import Clock
from app.application.ports.file_storage import FileStorageProvider
from app.application.ports.identifiers import IdGenerator
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.ports.upload_services import MimeDetector, UploadMetricsRecorder
from app.application.use_cases.auth import (
    AuthenticateAccessUseCase,
    BootstrapAdminUseCase,
    LoginUseCase,
    LogoutUseCase,
    RefreshSessionUseCase,
    RevokeAllSessionsUseCase,
)
from app.application.use_cases.storage import (
    AppendUploadChunkUseCase,
    CancelUploadUseCase,
    CompleteUploadUseCase,
    CopyEntryUseCase,
    CreateFolderUseCase,
    GetFileDetailsUseCase,
    GetUploadStatusUseCase,
    ListFolderEntriesUseCase,
    MoveEntryUseCase,
    PermanentlyDeleteUseCase,
    RenameEntryUseCase,
    RestoreEntryUseCase,
    StartUploadUseCase,
    TrashEntryUseCase,
)
from app.application.use_cases.storage.uploads import UploadUseCase
from app.application.use_cases.system import GetHealthUseCase, GetReadinessUseCase
from app.infrastructure.config import Settings
from app.infrastructure.persistence import Database, SQLAlchemyUnitOfWorkFactory
from app.infrastructure.persistence.health import SQLAlchemyDatabaseHealthProvider
from app.infrastructure.persistence.identifiers import Uuid7Generator
from app.infrastructure.persistence.repositories.auth import PostgreSQLRateLimiter
from app.infrastructure.security import (
    Argon2idPasswordHasher,
    HmacSecretTokenProvider,
    PyJwtProvider,
    SystemClock,
)
from app.infrastructure.storage import LocalFileStorageProvider
from app.infrastructure.storage.metrics import LoggingUploadMetricsRecorder
from app.infrastructure.storage.mime import SignatureMimeDetector


@dataclass(frozen=True, slots=True)
class ApplicationContainer:
    """Fully constructed application services exposed to presentation."""

    get_health: GetHealthUseCase
    get_readiness: GetReadinessUseCase
    unit_of_work_factory: UnitOfWorkFactory
    database: Database
    authenticate_access: AuthenticateAccessUseCase
    bootstrap_admin: BootstrapAdminUseCase
    login: LoginUseCase
    refresh_session: RefreshSessionUseCase
    logout: LogoutUseCase
    revoke_all_sessions: RevokeAllSessionsUseCase
    create_folder: CreateFolderUseCase
    rename_entry: RenameEntryUseCase
    move_entry: MoveEntryUseCase
    copy_entry: CopyEntryUseCase
    trash_entry: TrashEntryUseCase
    restore_entry: RestoreEntryUseCase
    permanently_delete: PermanentlyDeleteUseCase
    list_folder_entries: ListFolderEntriesUseCase
    get_file_details: GetFileDetailsUseCase
    start_upload: StartUploadUseCase
    get_upload_status: GetUploadStatusUseCase
    append_upload_chunk: AppendUploadChunkUseCase
    complete_upload: CompleteUploadUseCase
    cancel_upload: CancelUploadUseCase
    file_storage: FileStorageProvider

    @classmethod
    def build(cls, settings: Settings) -> "ApplicationContainer":
        """Create use cases and inject all configuration/adapters."""
        database = Database(settings)
        id_generator = Uuid7Generator()
        clock = SystemClock()
        secrets = HmacSecretTokenProvider(settings)
        password_hasher = Argon2idPasswordHasher(settings)
        jwt_provider = PyJwtProvider(settings)
        policy = AuthPolicyDTO(
            access_token_ttl_seconds=settings.access_token_ttl_seconds,
            refresh_token_ttl_seconds=settings.refresh_token_ttl_seconds,
            maximum_failed_logins=settings.maximum_failed_logins,
            account_lock_seconds=settings.account_lock_seconds,
            login_rate_limit=settings.login_rate_limit,
            login_rate_window_seconds=settings.login_rate_window_seconds,
            login_rate_block_seconds=settings.login_rate_block_seconds,
            refresh_rate_limit=settings.refresh_rate_limit,
            refresh_rate_window_seconds=settings.refresh_rate_window_seconds,
            refresh_rate_block_seconds=settings.refresh_rate_block_seconds,
            minimum_password_length=settings.minimum_password_length,
        )
        database_health = SQLAlchemyDatabaseHealthProvider(database.session_factory)
        unit_of_work_factory = SQLAlchemyUnitOfWorkFactory(
            database.session_factory,
            id_generator,
        )
        rate_limiter = PostgreSQLRateLimiter(
            database.session_factory,
            id_generator,
            secrets,
        )
        authenticate_access = AuthenticateAccessUseCase(
            unit_of_work_factory=unit_of_work_factory,
            jwt_provider=jwt_provider,
            secrets=secrets,
            clock=clock,
        )
        file_storage = LocalFileStorageProvider(settings.storage_root)
        upload_policy = UploadPolicyDTO(
            maximum_file_size=settings.max_upload_size_bytes,
            maximum_chunk_size=settings.max_upload_chunk_size_bytes,
            maximum_logical_path_length=settings.max_logical_path_length,
            session_ttl_seconds=settings.upload_session_ttl_seconds,
            allowed_extensions=_normalized_values(settings.upload_allowed_extensions),
            blocked_extensions=_normalized_values(settings.upload_blocked_extensions),
            allowed_mime_types=frozenset(
                value.strip().casefold()
                for value in settings.upload_allowed_mime_types
                if value.strip()
            ),
        )
        mime_detector = SignatureMimeDetector()
        upload_metrics = LoggingUploadMetricsRecorder()
        return cls(
            get_health=GetHealthUseCase(
                service_name=settings.app_name,
                version=settings.app_version,
            ),
            get_readiness=GetReadinessUseCase(database_health),
            unit_of_work_factory=unit_of_work_factory,
            database=database,
            authenticate_access=authenticate_access,
            bootstrap_admin=BootstrapAdminUseCase(
                unit_of_work_factory=unit_of_work_factory,
                password_hasher=password_hasher,
                id_generator=id_generator,
                clock=clock,
                secrets=secrets,
                policy=policy,
            ),
            login=LoginUseCase(
                unit_of_work_factory=unit_of_work_factory,
                rate_limiter=rate_limiter,
                password_hasher=password_hasher,
                jwt_provider=jwt_provider,
                secrets=secrets,
                id_generator=id_generator,
                clock=clock,
                policy=policy,
            ),
            refresh_session=RefreshSessionUseCase(
                unit_of_work_factory=unit_of_work_factory,
                rate_limiter=rate_limiter,
                jwt_provider=jwt_provider,
                secrets=secrets,
                id_generator=id_generator,
                clock=clock,
                policy=policy,
            ),
            logout=LogoutUseCase(
                unit_of_work_factory=unit_of_work_factory,
                id_generator=id_generator,
                secrets=secrets,
                clock=clock,
            ),
            revoke_all_sessions=RevokeAllSessionsUseCase(
                unit_of_work_factory=unit_of_work_factory,
                id_generator=id_generator,
                secrets=secrets,
                clock=clock,
            ),
            create_folder=CreateFolderUseCase(
                unit_of_work_factory=unit_of_work_factory,
                id_generator=id_generator,
                clock=clock,
            ),
            rename_entry=RenameEntryUseCase(
                unit_of_work_factory=unit_of_work_factory,
                id_generator=id_generator,
                clock=clock,
            ),
            move_entry=MoveEntryUseCase(
                unit_of_work_factory=unit_of_work_factory,
                id_generator=id_generator,
                clock=clock,
            ),
            copy_entry=CopyEntryUseCase(
                unit_of_work_factory=unit_of_work_factory,
                id_generator=id_generator,
                clock=clock,
            ),
            trash_entry=TrashEntryUseCase(
                unit_of_work_factory=unit_of_work_factory,
                id_generator=id_generator,
                clock=clock,
            ),
            restore_entry=RestoreEntryUseCase(
                unit_of_work_factory=unit_of_work_factory,
                id_generator=id_generator,
                clock=clock,
            ),
            permanently_delete=PermanentlyDeleteUseCase(
                unit_of_work_factory=unit_of_work_factory,
                id_generator=id_generator,
                clock=clock,
            ),
            list_folder_entries=ListFolderEntriesUseCase(unit_of_work_factory),
            get_file_details=GetFileDetailsUseCase(unit_of_work_factory),
            start_upload=_build_upload_use_case(
                StartUploadUseCase,
                unit_of_work_factory,
                file_storage,
                id_generator,
                clock,
                mime_detector,
                upload_metrics,
                upload_policy,
            ),
            get_upload_status=_build_upload_use_case(
                GetUploadStatusUseCase,
                unit_of_work_factory,
                file_storage,
                id_generator,
                clock,
                mime_detector,
                upload_metrics,
                upload_policy,
            ),
            append_upload_chunk=_build_upload_use_case(
                AppendUploadChunkUseCase,
                unit_of_work_factory,
                file_storage,
                id_generator,
                clock,
                mime_detector,
                upload_metrics,
                upload_policy,
            ),
            complete_upload=_build_upload_use_case(
                CompleteUploadUseCase,
                unit_of_work_factory,
                file_storage,
                id_generator,
                clock,
                mime_detector,
                upload_metrics,
                upload_policy,
            ),
            cancel_upload=_build_upload_use_case(
                CancelUploadUseCase,
                unit_of_work_factory,
                file_storage,
                id_generator,
                clock,
                mime_detector,
                upload_metrics,
                upload_policy,
            ),
            file_storage=file_storage,
        )


def _normalized_values(values: tuple[str, ...]) -> frozenset[str]:
    return frozenset(
        value.strip().removeprefix(".").casefold() for value in values if value.strip()
    )


def _build_upload_use_case[UploadUseCaseT: UploadUseCase](
    use_case_type: type[UploadUseCaseT],
    unit_of_work_factory: UnitOfWorkFactory,
    storage: FileStorageProvider,
    id_generator: IdGenerator,
    clock: Clock,
    mime_detector: MimeDetector,
    metrics: UploadMetricsRecorder,
    policy: UploadPolicyDTO,
) -> UploadUseCaseT:
    return use_case_type(
        unit_of_work_factory=unit_of_work_factory,
        storage=storage,
        id_generator=id_generator,
        clock=clock,
        mime_detector=mime_detector,
        metrics=metrics,
        policy=policy,
    )
