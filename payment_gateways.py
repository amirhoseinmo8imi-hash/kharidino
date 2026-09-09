"""Production payment provider adapters for Kharidino.

The module is intentionally provider-specific while ``payment.py`` remains
provider-neutral. Credentials are read only from environment variables.
"""
from __future__ import annotations

import logging
import os
from urllib.parse import quote

import requests


logger = logging.getLogger(__name__)


class NextPayGateway:
    """NextPay direct gateway adapter based on its published API contract."""

    name = "nextpay"
    callback_signature_required = False
    token_url = "https://nextpay.org/nx/gateway/token"
    verify_url = "https://nextpay.org/nx/gateway/verify"
    payment_url = "https://nextpay.org/nx/gateway/payment/{trans_id}"

    def __init__(self) -> None:
        self.api_key = os.environ.get("NEXTPAY_API_KEY", "").strip()
        if not self.api_key:
            raise RuntimeError("NEXTPAY_API_KEY is required when PAYMENT_PROVIDER=nextpay")
        try:
            self.timeout = max(2.0, min(float(os.environ.get("PAYMENT_HTTP_TIMEOUT", "10")), 30.0))
        except ValueError as exc:
            raise RuntimeError("PAYMENT_HTTP_TIMEOUT must be numeric") from exc

    @staticmethod
    def _safe_transaction(transaction_id: str) -> str:
        return transaction_id[:12] + "..." if transaction_id else "unknown"

    def start(self, transaction_id: str, amount: int, callback_url: str):
        from payment import GatewayStartResult

        payload = {
            "api_key": self.api_key,
            "order_id": transaction_id,
            "amount": int(amount),
            "callback_uri": callback_url,
            "currency": "IRT",
            "auto_verify": "no",
        }
        try:
            response = requests.post(self.token_url, data=payload, timeout=self.timeout)
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning(
                "NextPay start failed for transaction=%s: %s",
                self._safe_transaction(transaction_id),
                type(exc).__name__,
            )
            return GatewayStartResult("failed", "", "")

        code = body.get("code")
        trans_id = str(body.get("trans_id", "")).strip()
        if code != -1 or not trans_id:
            logger.warning(
                "NextPay token rejected for transaction=%s code=%r",
                self._safe_transaction(transaction_id),
                code,
            )
            return GatewayStartResult("failed", "", "")

        return GatewayStartResult(
            "redirect",
            self.payment_url.format(trans_id=quote(trans_id, safe="")),
            trans_id,
        )

    def verify(self, transaction_id: str, amount: int, payload: dict):
        from payment import GatewayVerifyResult

        # NextPay's trans_id is a provider-generated token and is deliberately
        # different from our internal transaction/order identifier. The
        # callback layer already binds this token to tx.authority before verify.
        trans_id = str(payload.get("trans_id", "")).strip()
        if not trans_id:
            return GatewayVerifyResult(False, "", "درگاه شناسه تراکنش را برنگرداند.")

        requested_amount = int(amount)
        provider_amount = str(payload.get("amount", "")).strip()
        if provider_amount and provider_amount.isdigit() and int(provider_amount) != requested_amount:
            return GatewayVerifyResult(False, "", "مبلغ بازگشتی درگاه با سفارش تطابق ندارد.")

        verify_payload = {
            "api_key": self.api_key,
            "trans_id": trans_id,
            "amount": requested_amount,
            "currency": "IRT",
        }
        try:
            response = requests.post(self.verify_url, data=verify_payload, timeout=self.timeout)
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning(
                "NextPay verify failed for transaction=%s: %s",
                self._safe_transaction(transaction_id),
                type(exc).__name__,
            )
            return GatewayVerifyResult(False, "", "استعلام درگاه با خطای شبکه مواجه شد؛ پرداخت دوباره قابل تلاش است.")

        code = body.get("code")
        provider_order = str(body.get("order_id", "")).strip()
        returned_amount = body.get("amount")
        if code != 0:
            logger.info(
                "NextPay verify rejected for transaction=%s code=%r",
                self._safe_transaction(transaction_id),
                code,
            )
            return GatewayVerifyResult(False, "", "پرداخت توسط درگاه تأیید نشد.")
        if not provider_order or provider_order != transaction_id:
            return GatewayVerifyResult(False, "", "شماره سفارش درگاه با تراکنش داخلی تطابق ندارد.")
        try:
            if returned_amount is None or int(returned_amount) != requested_amount:
                return GatewayVerifyResult(False, "", "مبلغ تأییدشده درگاه با سفارش تطابق ندارد.")
        except (TypeError, ValueError):
            return GatewayVerifyResult(False, "", "مبلغ پاسخ درگاه نامعتبر است.")

        reference = str(body.get("Shaparak_Ref_Id", "")).strip()
        if not reference:
            return GatewayVerifyResult(False, "", "درگاه مرجع پرداخت معتبری برنگرداند.")
        return GatewayVerifyResult(True, reference[:200])
