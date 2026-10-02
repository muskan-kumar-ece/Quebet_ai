import { NextRequest, NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_INTERNAL_URL || "http://localhost:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return forwardRequest(request, params.path);
}

export async function POST(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return forwardRequest(request, params.path);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return forwardRequest(request, params.path);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return forwardRequest(request, params.path);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return forwardRequest(request, params.path);
}

async function forwardRequest(request: NextRequest, pathSegments: string[]) {
  const targetPath = pathSegments.join("/");
  const searchParams = request.nextUrl.search;
  const targetUrl = `${FASTAPI_URL}/api/v1/${targetPath}${searchParams}`;

  try {
    const headers = new Headers();
    request.headers.forEach((value, key) => {
      if (key.toLowerCase() !== "host") {
        headers.set(key, value);
      }
    });

    let body: BodyInit | null = null;
    if (["POST", "PUT", "PATCH"].includes(request.method)) {
      body = await request.text();
    }

    const response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
    });

    const responseData = await response.text();

    return new NextResponse(responseData, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("Content-Type") || "application/json",
      },
    });
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        error: {
          code: "PROXY_BACKEND_UNREACHABLE",
          message: `Failed to connect to backend at ${FASTAPI_URL}: ${String(error)}`,
        },
      },
      { status: 502 }
    );
  }
}
