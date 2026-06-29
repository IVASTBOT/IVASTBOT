import { ChangeEvent, FormEvent, useMemo, useState } from "react";

interface VisionUploadProps {
  onRecognize: (input: { imagePath?: string; file?: File | null }) => void;
  loading?: boolean;
}

export function VisionUpload({ onRecognize, loading }: VisionUploadProps) {
  const [imagePath, setImagePath] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : ""), [file]);

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    onRecognize({ imagePath: imagePath.trim(), file });
  }

  return (
    <form className="vision-upload" onSubmit={submit}>
      <label>
        <span>image_path cho backend local</span>
        <input value={imagePath} onChange={(event) => setImagePath(event.target.value)} placeholder="/absolute/path/to/image.jpg" />
      </label>
      <label>
        <span>Preview file</span>
        <input type="file" accept="image/*" onChange={onFileChange} />
      </label>
      {previewUrl && <img className="image-preview" src={previewUrl} alt="Preview" />}
      <p className="hint">Backend MVP nhận `image_path`; upload file hiện dùng để preview trong trình duyệt.</p>
      <button type="submit" disabled={loading || (!imagePath.trim() && !file)}>
        Recognize
      </button>
    </form>
  );
}

