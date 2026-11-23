import logging

from ...domain.ports import AccountPort

logger = logging.getLogger(__name__)


class DeleteAccountUseCase:
    """
    Deletes the signed-in reader's account and all of their data (KVKK / GDPR erasure).
    The caller must confirm explicitly; the user is identified only by their verified JWT.
    """

    def __init__(self, account_port: AccountPort):
        self._account_port = account_port

    def execute(self, user_id: str, user_token: str, confirm: bool) -> None:
        if not user_id or not user_token:
            raise PermissionError("authentication required")
        if confirm is not True:
            raise ValueError("Account deletion must be confirmed with {\"confirm\": true}")
        self._account_port.delete_current_account(user_token)
        logger.info("Account deleted")  # no identifier: the person asked to be forgotten
