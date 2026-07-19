import pytest
from data_pipeline import process_data, filter_active_users


class TestDataPipeline:
    """Tests for the data processing pipeline."""

    def test_process_valid_data(self):
        """Test processing valid data."""
        data = [
            {"name": "Alice", "age": 25, "email": "ALICE@example.com"},
            {"name": "Bob", "age": 30, "email": "bob@test.com"},
        ]
        result = process_data(data)
        assert len(result) == 2
        assert result[0]["name"] == "ALICE"
        assert result[0]["age"] == 50
        assert result[0]["email"] == "alice@example.com"

    def test_process_null_values(self):
        """Test that null values are handled gracefully."""
        data = [
            {"name": "Alice", "age": 25, "email": "alice@example.com"},
            None,
            {"name": "Bob", "age": 30, "email": "bob@test.com"},
        ]
        # Should not crash on null values
        result = process_data(data)
        assert len(result) == 2  # Should skip null entries

    def test_process_empty_list(self):
        """Test with empty input."""
        result = process_data([])
        assert result == []

    def test_filter_active_users(self):
        """Test filtering active users."""
        users = [
            {"name": "Alice", "active": True},
            {"name": "Bob", "active": False},
            {"name": "Charlie", "active": True},
        ]
        result = filter_active_users(users)
        assert len(result) == 2
        assert all(u["active"] for u in result)

    def test_filter_with_null(self):
        """Test filtering with null entries."""
        users = [
            {"name": "Alice", "active": True},
            None,
            {"name": "Bob", "active": False},
        ]
        # Should not crash on null entries
        result = filter_active_users(users)
        assert len(result) == 1
        assert result[0]["name"] == "Alice"
