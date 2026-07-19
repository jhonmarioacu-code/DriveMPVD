import { beforeEach, describe, expect, it, vi, type MockInstance } from "vitest";

import {
  appendUploadChunk,
  cancelUpload,
  completeUpload,
  getUploadStatus,
  startUpload,
} from "@/features/uploads/api/uploads-api";
import type { UploadChunkResult, UploadSession } from "@/features/uploads/model/types";
import { apiClient } from "@/shared/api/client";

const session: UploadSession = {
  id: "upload-1",
  parent_id: "folder-1",
  filename: "informe.pdf",
  expected_size: 8,
  uploaded_bytes: 0,
  declared_mime_type: "application/pdf",
  extension: "pdf",
  status: "created",
  expires_at: "2026-07-19T18:00:00Z",
  checksum_sha256: null,
};

const chunkResult: UploadChunkResult = {
  upload_id: session.id,
  offset: 8,
  received_bytes: 8,
  chunk_sha256: "checksum",
};

describe("uploads api", () => {
  let request: MockInstance<typeof apiClient.request>;
  let requestHeaders: MockInstance<typeof apiClient.requestHeaders>;
  let requestWithUploadProgress: MockInstance<
    typeof apiClient.requestWithUploadProgress
  >;

  beforeEach(() => {
    request = vi.spyOn(apiClient, "request").mockResolvedValue(session);
    requestHeaders = vi.spyOn(apiClient, "requestHeaders").mockResolvedValue(
      new Headers({
        "Upload-Offset": "0",
        "Upload-Length": "8",
        "Upload-Status": "created",
        "Upload-Expires": session.expires_at,
      }),
    );
    requestWithUploadProgress = vi
      .spyOn(apiClient, "requestWithUploadProgress")
      .mockResolvedValue(chunkResult);
  });

  it("crea una sesión con los metadatos exactos del archivo", async () => {
    const file = new File(["contenido"], "informe.pdf", {
      type: "application/pdf",
    });

    await expect(startUpload("folder-1", file)).resolves.toEqual(session);

    expect(request).toHaveBeenCalledWith("/storage/uploads", {
      method: "POST",
      signal: undefined,
      body: JSON.stringify({
        parent_id: "folder-1",
        filename: "informe.pdf",
        size: file.size,
        mime_type: "application/pdf",
      }),
    });
  });

  it("usa un tipo binario seguro cuando el navegador no informa MIME", async () => {
    const file = new File(["contenido"], "sin-extension");

    await startUpload("folder-1", file);

    expect(request).toHaveBeenCalledWith("/storage/uploads", {
      method: "POST",
      signal: undefined,
      body: JSON.stringify({
        parent_id: "folder-1",
        filename: "sin-extension",
        size: file.size,
        mime_type: "application/octet-stream",
      }),
    });
  });

  it("lee el estado reanudable desde las cabeceras HEAD", async () => {
    requestHeaders.mockResolvedValueOnce(
      new Headers({
        "Upload-Offset": "4",
        "Upload-Length": "8",
        "Upload-Status": "uploading",
        "Upload-Expires": session.expires_at,
      }),
    );

    await expect(getUploadStatus("upload / one")).resolves.toEqual({
      uploadedBytes: 4,
      expectedSize: 8,
      state: "uploading",
      expiresAt: session.expires_at,
    });
    expect(requestHeaders).toHaveBeenCalledWith("/storage/uploads/upload%20%2F%20one", {
      method: "HEAD",
      signal: undefined,
    });
  });

  it("rechaza cabeceras de estado incompletas o inválidas", async () => {
    requestHeaders.mockResolvedValueOnce(
      new Headers({
        "Upload-Offset": "not-a-number",
        "Upload-Length": "8",
        "Upload-Status": "uploading",
        "Upload-Expires": session.expires_at,
      }),
    );

    await expect(getUploadStatus(session.id)).rejects.toMatchObject({
      code: "client.invalid_upload_status",
      status: 502,
    });

    requestHeaders.mockResolvedValueOnce(
      new Headers({
        "Upload-Offset": "4",
        "Upload-Length": "8",
        "Upload-Status": "unknown",
        "Upload-Expires": session.expires_at,
      }),
    );

    await expect(getUploadStatus(session.id)).rejects.toMatchObject({
      code: "client.invalid_upload_status",
    });
  });

  it("envía cada bloque con offset y progreso acumulado", async () => {
    const controller = new AbortController();
    const chunk = new Blob(["contenido"]);
    const reportProgress = vi.fn();

    await expect(
      appendUploadChunk("upload / one", 12, chunk, controller.signal, reportProgress),
    ).resolves.toEqual(chunkResult);

    const [path, sentChunk, init, options] =
      requestWithUploadProgress.mock.calls[0] ?? [];
    expect(path).toBe("/storage/uploads/upload%20%2F%20one");
    expect(sentChunk).toBe(chunk);
    expect(init).toEqual({
      method: "PATCH",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/offset+octet-stream",
        "Upload-Offset": "12",
      },
    });
    expect(options?.onProgress).toEqual(expect.any(Function));
    options?.onProgress?.({ loaded: 3, total: chunk.size });
    expect(reportProgress).toHaveBeenCalledWith(15);
  });

  it("completa y cancela con las rutas del contrato", async () => {
    const completedEntry = { id: "file-1", kind: "file" };
    request.mockResolvedValueOnce(completedEntry).mockResolvedValueOnce(session);

    await expect(completeUpload("upload / one")).resolves.toEqual(completedEntry);
    await expect(cancelUpload("upload / one")).resolves.toEqual(session);

    expect(request).toHaveBeenNthCalledWith(
      1,
      "/storage/uploads/upload%20%2F%20one/complete",
      {
        method: "POST",
        signal: undefined,
      },
    );
    expect(request).toHaveBeenNthCalledWith(2, "/storage/uploads/upload%20%2F%20one", {
      method: "DELETE",
    });
  });
});
