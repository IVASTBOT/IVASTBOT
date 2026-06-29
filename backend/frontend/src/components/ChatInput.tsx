import { FormEvent, useState } from "react";

interface ChatInputProps {
  onSubmit: (value: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSubmit, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue("");
  }

  return (
    <form className="chat-input" onSubmit={submit}>
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Nhập câu hỏi cho IVASTBOT..."
        disabled={disabled}
      />
      <button type="submit" disabled={disabled || !value.trim()}>
        Gửi
      </button>
    </form>
  );
}

