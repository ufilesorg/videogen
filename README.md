# Stock Photo Proxy Application

## Overview
This is a FastAPI-based proxy application that enables users to search and download stock photos from multiple stock websites. The application acts as an intermediary, making it easier for users to access a variety of stock photos without needing to visit each site individually.

## Features
- **Search Stock Photos**: Users can search for stock photos using keywords.
- **Download Photos**: Allows users to download high-quality stock photos directly through the application.
- **Multiple Stock Websites**: Integrates with various popular stock photo websites to provide a wide range of photos.
- **FastAPI Framework**: Built using FastAPI for high performance and easy scalability.
## Installation

### Prerequisites
- Docker
- Docker Compose

### Steps
1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/stock-photo-proxy.git
    ```
2. Navigate to the project directory:
    ```sh
    cd stock-photo-proxy
    ```
3. Create a `.env` file from `sample.env` and configure your environment variables:
    ```sh
    cp sample.env .env
    ```
4. Build and start the application using Docker Compose:
    ```sh
    docker-compose up --build
    ```

## Usage
1. Start the server using Docker Compose:
    ```sh
    docker-compose up
    ```
2. Access the API documentation at `http://127.0.0.1:8000/docs` to explore the available endpoints and test the API.

## Endpoints
- **GET /search**: Search for stock photos using keywords.
- **GET /download**: Download a stock photo by specifying the photo ID.

## Contributing
Contributions are welcome! Please open an issue or submit a pull request with your changes.

## License
This project is licensed under the MIT License. See the `LICENSE` file for more details.

## Contact
For any questions or feedback, please create issue.