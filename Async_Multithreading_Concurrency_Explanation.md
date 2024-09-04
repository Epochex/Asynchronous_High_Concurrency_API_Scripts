
# Asynchronous and Multithreading Concurrency for Multiple Server Fetching

This document provides a detailed explanation of a Python script designed to efficiently fetch data from multiple target servers using both asynchronous programming (via `asyncio` and `aiohttp`) and multithreading (`ThreadPoolExecutor`). The system aims to optimize performance in low-resource environments, such as SaaS platforms, bastion hosts, or edge devices, where resources are constrained but high efficiency is still required.

## Table of Contents

- [Asynchronous and Multithreading Concurrency for Multiple Server Fetching](#asynchronous-and-multithreading-concurrency-for-multiple-server-fetching)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Key Components](#key-components)
  - [Asynchronous Logic](#asynchronous-logic)
    - [1. Fetching Data Asynchronously](#1-fetching-data-asynchronously)
    - [2. Asynchronous Data Processing](#2-asynchronous-data-processing)
  - [Thread Pool and Concurrency](#thread-pool-and-concurrency)
  - [Rate Limiting and Progress Tracking](#rate-limiting-and-progress-tracking)
  - [Error Handling](#error-handling)
  - [Writing Results to CSV](#writing-results-to-csv)


---

## Overview

The script fetches Electronic Shelf Label (ESL) data from multiple servers asynchronously. It uses both asynchronous programming to handle high I/O-bound operations (HTTP requests) and a thread pool for parallelism across multiple target servers. It fetches ESL data and processes it concurrently while managing progress via a visual progress bar.

The combination of asynchronous logic and a multithreaded thread pool enables the script to perform multiple HTTP requests concurrently while efficiently utilizing the system's resources.

---

## Key Components

- **aiohttp**: Provides an asynchronous HTTP client to handle HTTP requests without blocking the main event loop.
- **asyncio**: Handles asynchronous operations, allowing for non-blocking execution of tasks.
- **ThreadPoolExecutor**: Enables multithreading, allowing the script to spawn threads that run different tasks concurrently.
- **tqdm**: A progress bar library that tracks and visualizes the progress of async operations.

---

## Asynchronous Logic

### 1. Fetching Data Asynchronously

The core of the script revolves around making asynchronous HTTP requests using `aiohttp` in an `asyncio` event loop. This allows multiple requests to be processed in a non-blocking fashion, ideal for I/O-bound operations such as fetching data from APIs.

The function `fetch_store_data` is responsible for asynchronously retrieving data from each store:

```python
async def fetch_store_data(session, eslworking, store, index, semaphore):
    async with semaphore:
        try:
            url = f'http://{eslworking}/api3/{store}/esls/page/{index}'
            async with session.get(url) as response:
                return await response.json()
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None
```

- **Semaphore**: A semaphore is used to limit the number of concurrent requests, preventing the system from being overwhelmed by too many simultaneous operations.
- **aiohttp.ClientSession**: The asynchronous HTTP client is used to manage requests and responses in an efficient manner.

### 2. Asynchronous Data Processing

The function `process_store` processes data for a specific store, fetching ESL records in pages. It uses the `fetch_store_data` function to make paginated requests, retrieves detailed ESL data, and processes them concurrently.

```python
async def process_store(session, eslworking, store, max_records_per_store, yesterday_str, semaphore, pbar):
    ...
    # Fetches ESL data and appends results to store_results
    store_data = await fetch_store_data(session, eslworking, store['user'], index, semaphore)
    ...
```

The loop in `process_store` ensures that all pages of ESL data are fetched for a given store. The script breaks out of the loop once all data has been fetched or the maximum number of records is reached.

---

## Thread Pool and Concurrency

The script handles multiple servers concurrently using a `ThreadPoolExecutor`. This allows several tasks to run in parallel, with each thread responsible for fetching data from one or more servers.

```python
with ThreadPoolExecutor(max_workers=3) as executor:
    futures = [
        executor.submit(loop.run_until_complete, code(eslworking, max_records_per_store, semaphore))
        for eslworking in eslworkingLists[start_index:end_index]
    ]
    for future in as_completed(futures):
        try:
            result = future.result()
            list_resultat.extend(result)
        except Exception as e:
            print(f"Thread raised an exception: {e}")
```

- **ThreadPoolExecutor**: Spawns threads for each target server.
- **Concurrency**: Each thread runs an event loop (`loop.run_until_complete`) that asynchronously fetches data from its assigned server.

---

## Rate Limiting and Progress Tracking

A semaphore limits the number of concurrent requests to prevent overwhelming the server. In this script, the semaphore is initialized with a maximum of 4 concurrent requests:

```python
semaphore = asyncio.Semaphore(max_concurrent_requests)
```

Additionally, the script uses the `tqdm` library to visualize progress:

```python
with tqdm(total=total_esls, desc=f"Processing {eslworking}", unit="esl") as pbar:
```

The progress bar updates as each ESL data fetch completes, providing real-time feedback on the progress of the data fetching process.

---

## Error Handling

Error handling is integrated into both the asynchronous fetch functions and the thread pool executor to ensure robustness. If an error occurs during a request, the error is caught, logged, and the process continues without crashing.

For example, in the `fetch_store_data` function:

```python
except Exception as e:
    print(f"Error fetching {url}: {e}")
    return None
```

The same approach is used in the thread pool to catch exceptions raised by individual threads.

---

## Writing Results to CSV

After fetching and processing the data, the results are written to CSV files. The function `write_to_csv` saves the ESL data to disk, sorted by a specified criterion:

```python
df = pd.DataFrame(list_resultat)
df = df.sort_values(by='frequency', ascending=True)
filename = f'esl_id_part_{file_index + 1}.csv'
df.to_csv(filename, index=False, encoding='utf-8')
```

This function ensures that data is written in a structured and accessible format.

---


