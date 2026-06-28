# Sync status message formatting

The final sync message now renders each action on its own line and prefixes it with an emoji:

- `📥` for installed subscribed decks
- `🔄` for synced card changes
- `🧹` for reconciled removed cards
- `🗑️` for removed local tracking of unsubscribed decks

This keeps long deck names readable and makes mixed sync outcomes easier to scan.
