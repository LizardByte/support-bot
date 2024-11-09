# standard imports
import os
from datetime import datetime, UTC

# lib imports
from cryptography import x509
import pytest

# local imports
from src.common.crypto import check_expiration, generate_certificate, initialize_certificate, CERT_FILE, KEY_FILE


@pytest.fixture(scope='module')
def setup_certificates():
    # Ensure the certificates are generated for testing
    if not os.path.exists(CERT_FILE) or not os.path.exists(KEY_FILE):
        generate_certificate()
    yield
    # Cleanup after tests
    if os.path.exists(CERT_FILE):
        os.remove(CERT_FILE)
    if os.path.exists(KEY_FILE):
        os.remove(KEY_FILE)


def test_check_expiration(setup_certificates):
    days_left = check_expiration(CERT_FILE)
    assert days_left <= 365
    assert days_left >= 364


def test_check_expiration_expired():
    cert_file = os.path.join("tests", "fixtures", "certs", "expired", "cert.pem")
    days_left = check_expiration(cert_file)
    assert days_left < 0


def test_generate_certificate(setup_certificates):
    assert os.path.exists(CERT_FILE)
    assert os.path.exists(KEY_FILE)

    with open(CERT_FILE, "rb") as cert_file:
        cert_data = cert_file.read()

    cert = x509.load_pem_x509_certificate(cert_data)
    assert cert.not_valid_after_utc > datetime.now(UTC)


def test_initialize_certificate(setup_certificates):
    cert_file, key_file = initialize_certificate()
    assert os.path.exists(cert_file)
    assert os.path.exists(key_file)

    cert_expires_in = check_expiration(cert_file)
    assert cert_expires_in <= 365
    assert cert_expires_in >= 364
