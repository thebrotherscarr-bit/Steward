package messaging

import (
	"atlas/webapp/db"
)

type Bus struct {
	db *db.DB
}

func NewBus() *Bus {
	return &Bus{}
}

func (b *Bus) SetDB(database *db.DB) {
	b.db = database
}

func (b *Bus) Send(m db.Message) {
	if b.db != nil {
		b.db.AddMessage(m)
	}
}

func (b *Bus) List(channel string, limit int) []db.Message {
	if b.db != nil {
		return b.db.GetMessages(channel, limit)
	}
	return nil
}

type Adapter interface {
	Name() string
	Send(channel, content string) error
	Listen(handler func(channel, sender, content string)) error
	Stop() error
}

type DiscordAdapter struct {
	token string
}

func NewDiscordAdapter(token string) *DiscordAdapter {
	return &DiscordAdapter{token: token}
}

func (d *DiscordAdapter) Name() string { return "discord" }

func (d *DiscordAdapter) Send(channel, content string) error {
	return nil
}

func (d *DiscordAdapter) Listen(handler func(channel, sender, content string)) error {
	return nil
}

func (d *DiscordAdapter) Stop() error { return nil }

type SlackAdapter struct {
	token string
}

func NewSlackAdapter(token string) *SlackAdapter {
	return &SlackAdapter{token: token}
}

func (s *SlackAdapter) Name() string { return "slack" }

func (s *SlackAdapter) Send(channel, content string) error {
	return nil
}

func (s *SlackAdapter) Listen(handler func(channel, sender, content string)) error {
	return nil
}

func (s *SlackAdapter) Stop() error { return nil }

type WhatsAppAdapter struct {
	phoneNumberID string
	token         string
}

func NewWhatsAppAdapter(phoneID, token string) *WhatsAppAdapter {
	return &WhatsAppAdapter{phoneNumberID: phoneID, token: token}
}

func (w *WhatsAppAdapter) Name() string { return "whatsapp" }

func (w *WhatsAppAdapter) Send(channel, content string) error {
	return nil
}

func (w *WhatsAppAdapter) Listen(handler func(channel, sender, content string)) error {
	return nil
}

func (w *WhatsAppAdapter) Stop() error { return nil }
