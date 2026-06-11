import json

from agent_hub.agents.movie_recommender.omdb import fetch_rotten_tomatoes_score
from agent_hub.core.config import HubConfig, OmdbConfig


def test_fetch_rotten_tomatoes_score(hub_config, monkeypatch):
    config = HubConfig(
        data_dir=hub_config.data_dir,
        omdb=OmdbConfig(api_key="test-omdb-key"),
    )

    def fake_urlopen(request, timeout=15):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(
                    {
                        "Response": "True",
                        "imdbRating": "8.7/10",
                        "Ratings": [
                            {"Source": "Internet Movie Database", "Value": "8.7/10"},
                            {"Source": "Rotten Tomatoes", "Value": "87%"},
                            {"Source": "Metacritic", "Value": "73/100"},
                        ],
                    }
                ).encode("utf-8")

        return FakeResponse()

    monkeypatch.setattr("agent_hub.agents.movie_recommender.omdb.urllib.request.urlopen", fake_urlopen)

    from agent_hub.agents.movie_recommender.omdb import fetch_omdb_details

    details = fetch_omdb_details("tt0133093", config=config)
    assert details is not None
    assert details.rotten_tomatoes_score == "87%"
    assert details.metacritic_score == "73/100"
    assert details.imdb_rating == "8.7/10"


def test_fetch_rotten_tomatoes_score_without_api_key(hub_config):
    config = HubConfig(data_dir=hub_config.data_dir, omdb=OmdbConfig(api_key=""))
    assert fetch_rotten_tomatoes_score("tt0133093", config=config) is None
