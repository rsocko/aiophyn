"""Tests for the API class initialization and module structure."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from aiophyn.api import API
from aiophyn.device import Device
from aiophyn.home import Home
from aiophyn.home_inventory import HomeInventory
from aiophyn.errors import BrandError, RequestError, PhynError


class TestAPIInit:
    """Tests for API class initialization."""

    def test_phyn_brand(self):
        """Verify phyn brand initializes correctly."""
        api = API("user@example.com", "password", phyn_brand="phyn")
        assert api._brand == 0
        assert api._username == "user@example.com"

    def test_kohler_brand(self):
        """Verify kohler brand initializes correctly."""
        api = API("user@example.com", "password", phyn_brand="kohler")
        assert api._brand == 1

    def test_invalid_brand_raises(self):
        """Verify invalid brand raises BrandError."""
        with pytest.raises(BrandError):
            API("user@example.com", "password", phyn_brand="invalid")

    def test_has_device_attribute(self):
        """Verify API has device handler."""
        api = API("user@example.com", "password", phyn_brand="phyn")
        assert isinstance(api.device, Device)

    def test_has_home_attribute(self):
        """Verify API has home handler."""
        api = API("user@example.com", "password", phyn_brand="phyn")
        assert isinstance(api.home, Home)

    def test_has_home_inventory_attribute(self):
        """Verify API has home_inventory handler."""
        api = API("user@example.com", "password", phyn_brand="phyn")
        assert isinstance(api.home_inventory, HomeInventory)

    def test_username_property(self):
        """Verify username property works."""
        api = API("user@example.com", "password", phyn_brand="phyn")
        assert api.username == "user@example.com"


class TestErrors:
    """Tests for error hierarchy."""

    def test_request_error_is_phyn_error(self):
        """RequestError should inherit from PhynError."""
        assert issubclass(RequestError, PhynError)

    def test_brand_error_is_exception(self):
        """BrandError should inherit from Exception."""
        assert issubclass(BrandError, Exception)

    def test_phyn_error_is_exception(self):
        """PhynError should inherit from Exception."""
        assert issubclass(PhynError, Exception)


class TestModuleExports:
    """Tests for package-level exports."""

    def test_async_get_api_importable(self):
        from aiophyn import async_get_api
        assert callable(async_get_api)

    def test_home_inventory_importable(self):
        from aiophyn import HomeInventory
        assert HomeInventory is not None
